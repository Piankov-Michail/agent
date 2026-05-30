from langchain.agents import create_agent
from models import ModelFabric

from abc import ABC, abstractmethod

class AgentFabric(ABC):
	@abstractmethod
	def get_agent(self, model, tools: list):
		pass

class DefaultAgentFactory(AgentFabric):
	@classmethod
	def get_agent(self, model, tools: list):
		return create_agent(model=model, tools=tools)