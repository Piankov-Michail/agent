import json as _json
import chainlit.langchain.callbacks as _cl_cb
import chainlit as cl
from agents import DefaultAgentFactory
from models import OllamaCloudFactory
from tools import create_tavily_search
from langchain.messages import AIMessageChunk
from langchain_core.runnables import RunnableConfig
from middleware import DateTimeMiddleware

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
DEFAULT_TIMEZONE = os.getenv('DEFAULT_TIMEZONE', '').strip() or None


@cl.on_chat_start
async def start():
    model = OllamaCloudFactory.get_model(
        model=OLLAMA_CLOUD_MODEL,
        base_url=OLLAMA_CLOUD_ENDPOINT,
        token=OLLAMA_API_KEY,
    )
    tools = [create_tavily_search(TavilyClient(api_key=TAVILY_API))]

    timezone = _detect_timezone()
    middleware = DateTimeMiddleware(timezone_name=timezone)

    agent = DefaultAgentFactory.get_agent(
        model=model,
        tools=tools,
        middleware=[middleware],
    )
    cl.user_session.set("agent", agent)


@cl.on_message
async def main(message: cl.Message):
    agent = cl.user_session.get("agent")

    msg = cl.Message(content="")
    cb = cl.AsyncLangchainCallbackHandler(stream_final_answer=False)

    async for event in agent.astream(
        {"messages": [("user", message.content)]},
        stream_mode="messages",
        config=RunnableConfig(callbacks=[cb]),
    ):
        if not isinstance(event, tuple) or len(event) != 2:
            continue
        chunk, _ = event
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            await msg.stream_token(chunk.content)

    await msg.send()


def _detect_timezone() -> str | None:
    if DEFAULT_TIMEZONE:
        return DEFAULT_TIMEZONE
    try:
        return datetime.now().astimezone().tzname()
    except Exception:
        return None
