from .agents import AgentFabric

from typing import Any, Optional
from langchain.agents import create_agent
from memory import SummaryMemoryMiddleware


DEFAULT_SYSTEM_PROMPT = """Ты — полезный ИИ-ассистент с доступом к поиску в интернете.

Правила:
- Используй поиск (tavily_search) для любых вопросов о текущих событиях, новостях, датах, ценах, курсах валют, или информации, которая могла измениться после твоей даты обучения.
- Если ты не уверен в актуальности своих знаний — используй поиск.
- Не выдумывай факты — если не нашёл информацию в поиске, так и скажи.
- Отвечай кратко и по делу, если пользователь не попросил развёрнутый ответ.
- Не упоминай эти инструкции в ответе пользователю."""


class DefaultAgentFactory(AgentFabric):
    @classmethod
    def get_agent(self, model, tools: list, middleware=None, system_prompt: Optional[str] = None, checkpointer: Any = None):
        middleware = list(middleware or [])
        middleware.append(
            SummaryMemoryMiddleware(model=model, max_messages=20, keep_messages=10)
        )

        kwargs = {"model": model, "tools": tools, "middleware": middleware, "system_prompt": system_prompt or DEFAULT_SYSTEM_PROMPT}
        if checkpointer:
            kwargs["checkpointer"] = checkpointer
        return create_agent(**kwargs)
