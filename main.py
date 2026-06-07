import asyncio
from agents import DefaultAgentFactory
from models import OllamaCloudFactory
from tools import create_tavily_search
from middleware import DateTimeMiddleware
from memory import create_checkpointer

from tavily import TavilyClient

import dotenv
import os
from datetime import datetime

dotenv.load_dotenv()

OLLAMA_API_KEY = os.getenv('OLLAMA_API_KEY')
OLLAMA_CLOUD_MODEL = os.getenv('OLLAMA_CLOUD_MODEL')
OLLAMA_CLOUD_ENDPOINT = os.getenv('OLLAMA_CLOUD_ENDPOINT')
DB_URI = os.getenv('DB_URI')
TAVILY_API = os.getenv('TAVILY_API')
DEFAULT_TIMEZONE = os.getenv('DEFAULT_TIMEZONE', '').strip() or None

THREAD_ID = "cli-default"


class Agent:
    def __init__(self):
        self._agent = None
        self._initialized = False

    async def _ensure(self):
        if self._initialized:
            return
        model = OllamaCloudFactory.get_model(
            model=OLLAMA_CLOUD_MODEL,
            base_url=OLLAMA_CLOUD_ENDPOINT,
            token=OLLAMA_API_KEY,
        )
        tools = [create_tavily_search(TavilyClient(api_key=TAVILY_API))]
        timezone = DEFAULT_TIMEZONE or datetime.now().astimezone().tzname()
        middleware = DateTimeMiddleware(timezone_name=timezone)
        checkpointer = await create_checkpointer(DB_URI)
        self._agent = DefaultAgentFactory.get_agent(
            model=model,
            tools=tools,
            middleware=[middleware],
            checkpointer=checkpointer,
        )
        self._initialized = True

    async def run_query(self, user_query: str):
        await self._ensure()
        result = await self._agent.ainvoke(
            {"messages": [("user", user_query)]},
            config={"configurable": {"thread_id": THREAD_ID}},
        )
        return result["messages"][-1].content


async def main():
    agent = Agent()
    while True:
        query = await asyncio.to_thread(input, "USER: ")
        print(f"AI: {await agent.run_query(query)}")


if __name__ == "__main__":
    asyncio.run(main())
