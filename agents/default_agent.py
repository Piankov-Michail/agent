from .agents import AgentFabric

from typing import Optional
from langchain.agents import create_agent

class DefaultAgentFactory(AgentFabric):
    @classmethod
    def get_agent(self, model, tools: list, middleware=None, system_prompt: Optional[str] = None):
        kwargs = {"model": model, "tools": tools}
        if system_prompt:
            kwargs["system_prompt"] = system_prompt
        if middleware:
            kwargs["middleware"] = middleware
        return create_agent(**kwargs)