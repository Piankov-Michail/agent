from abc import ABC, abstractmethod
from typing import Optional

from langchain.agents import create_agent


class AgentFabric(ABC):
    @abstractmethod
    def get_agent(self, model, tools: list, middleware=None, system_prompt=None):
        pass