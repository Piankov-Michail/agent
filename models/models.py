from langchain_ollama import ChatOllama

from abc import ABC, abstractmethod


class ModelFabric(ABC):
    @abstractmethod
    def get_model(self, model: str, base_url: str, token: str):
        pass