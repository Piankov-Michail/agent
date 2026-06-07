from agents import DefaultAgentFactory
from models import OllamaCloudFactory
from tools import create_tavily_search
from middleware import DateTimeMiddleware

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


class Agent:
    def __init__(self):
        model = OllamaCloudFactory.get_model(
            model=OLLAMA_CLOUD_MODEL,
            base_url=OLLAMA_CLOUD_ENDPOINT,
            token=OLLAMA_API_KEY,
        )
        tools = [create_tavily_search(TavilyClient(api_key=TAVILY_API))]
        timezone = DEFAULT_TIMEZONE or datetime.now().astimezone().tzname()
        middleware = DateTimeMiddleware(timezone_name=timezone)
        self.agent = DefaultAgentFactory.get_agent(
            model=model,
            tools=tools,
            middleware=[middleware],
        )

    def run_query(self, user_query: str):
        result = self.agent.invoke({"messages": [("user", user_query)]})
        return result["messages"][-1].content


if __name__ == "__main__":
    agent = Agent()
    while True:
        query = input("USER: ")
        print(f"AI: {agent.run_query(query)}")
