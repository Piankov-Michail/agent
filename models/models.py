from langchain_ollama import ChatOllama

from abc import ABC, abstractmethod

class ModelFabric(ABC):
	@abstractmethod
	def get_model(self, model: str, base_url: str, token: str):
		pass

class OllamaCloudFactory(ModelFabric):
	@classmethod
	def get_model(self, model: str, base_url: str, token: str):
		if token is None:
			return ValueError
		return ChatOllama(
            model=model,
            base_url=base_url,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {token}"
                }
            }
        )