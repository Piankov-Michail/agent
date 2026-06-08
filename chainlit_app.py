import json as _json
import uuid
import chainlit.langchain.callbacks as _cl_cb
import chainlit as cl
from agents import DefaultAgentFactory
from models import OllamaCloudFactory
from tools import create_tavily_search
from langchain.messages import AIMessageChunk
from langchain_core.runnables import RunnableConfig
from middleware import DateTimeMiddleware
from memory import create_checkpointer
from chainlit.types import ThreadDict
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit_db import init_chainlit_database

from tavily import TavilyClient

import dotenv
import os
from datetime import datetime

_original_dumps = _cl_cb.dumps
def _fixed_dumps(obj, *, pretty=False, **kwargs):
    kwargs.setdefault("ensure_ascii", False)
    return _original_dumps(obj, pretty=pretty, **kwargs)
_cl_cb.dumps = _fixed_dumps

dotenv.load_dotenv()

OLLAMA_API_KEY = os.getenv('OLLAMA_API_KEY')
OLLAMA_CLOUD_MODEL = os.getenv('OLLAMA_CLOUD_MODEL')
OLLAMA_CLOUD_ENDPOINT = os.getenv('OLLAMA_CLOUD_ENDPOINT')
TAVILY_API = os.getenv('TAVILY_API')
DB_URI = os.getenv('DB_URI')
DEFAULT_TIMEZONE = os.getenv('DEFAULT_TIMEZONE', '').strip() or None
CHAINLIT_AUTH_SECRET = os.getenv('CHAINLIT_AUTH_SECRET')
CHAINLIT_DB_URI = os.getenv('CHAINLIT_DB_URI')


_checkpointer = None
_agent = None


async def _get_checkpointer():
    global _checkpointer
    try:
        if _checkpointer is None:
            _checkpointer = await create_checkpointer(db_uri=DB_URI)
    except Exception as e:
        print(f"Warning: Checkpointer failed ({e}), falling back to MemorySaver", flush=True)
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()
    return _checkpointer


def _detect_timezone() -> str | None:
    if DEFAULT_TIMEZONE:
        return DEFAULT_TIMEZONE
    try:
        return datetime.now().astimezone().tzname()
    except Exception:
        return None


async def _get_or_create_agent():
    global _agent
    if _agent is not None:
        return _agent
    model = OllamaCloudFactory.get_model(
        model=OLLAMA_CLOUD_MODEL,
        base_url=OLLAMA_CLOUD_ENDPOINT,
        token=OLLAMA_API_KEY,
    )
    tools = [create_tavily_search(TavilyClient(api_key=TAVILY_API))]
    timezone = _detect_timezone()
    middleware = DateTimeMiddleware(timezone_name=timezone)
    checkpointer = await _get_checkpointer()
    _agent = DefaultAgentFactory.get_agent(
        model=model,
        tools=tools,
        middleware=[middleware],
        checkpointer=checkpointer,
    )
    return _agent


@cl.on_app_startup
async def init_database():
    await init_chainlit_database(CHAINLIT_DB_URI)


@cl.data_layer
def data_layer():
    return SQLAlchemyDataLayer(
        conninfo=CHAINLIT_DB_URI,
        show_logger=True,
    )


@cl.password_auth_callback
async def auth_callback(username: str, password: str) -> cl.User | None:
    if not CHAINLIT_AUTH_SECRET:
        return None
    return cl.User(identifier=username, metadata={"provider": "credentials"})


@cl.on_chat_start
async def start():
    agent = await _get_or_create_agent()
    session_id = cl.user_session.get("session_id") or str(uuid.uuid4())
    chat_id = str(uuid.uuid4())
    thread_id = f"{session_id}::{chat_id}"
    cl.user_session.set("agent", agent)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("chat_id", chat_id)
    cl.user_session.set("thread_id", thread_id)


@cl.on_chat_resume
async def resume(thread: ThreadDict):
    agent = await _get_or_create_agent()
    session_id = cl.user_session.get("session_id") or thread.get("metadata", {}).get("session_id", str(uuid.uuid4()))
    chat_id = cl.user_session.get("chat_id") or thread.get("metadata", {}).get("chat_id", str(uuid.uuid4()))
    thread_id = f"{session_id}::{chat_id}"
    cl.user_session.set("agent", agent)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("chat_id", chat_id)
    cl.user_session.set("thread_id", thread_id)


@cl.on_message
async def main(message: cl.Message):
    agent = cl.user_session.get("agent")
    thread_id = cl.user_session.get("thread_id")

    msg = cl.Message(content="")
    cb = cl.AsyncLangchainCallbackHandler(stream_final_answer=False)

    config = RunnableConfig(callbacks=[cb], configurable={"thread_id": thread_id})

    async for event in agent.astream(
        {"messages": [("user", message.content)]},
        stream_mode="messages",
        config=config,
    ):
        if not isinstance(event, tuple) or len(event) != 2:
            continue
        chunk, _ = event
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            await msg.stream_token(chunk.content)

    await msg.send()
