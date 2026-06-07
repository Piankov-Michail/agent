import uuid
from typing import Any, Optional

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain_core.messages import AnyMessage, SystemMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime


PROMPT = """Summarize the conversation history below. Preserve key decisions, user goals, and important context. Output only the summary.

{messages}"""


class SummaryMemoryMiddleware(AgentMiddleware[AgentState[Any], Any, Any]):
    def __init__(
        self,
        model,
        *,
        max_messages: int = 20,
        keep_messages: int = 10,
        prompt: str = PROMPT,
    ):
        super().__init__()
        self.model = model
        self.max_messages = max_messages
        self.keep_messages = keep_messages
        self.prompt = prompt

    def _ensure_ids(self, messages: list[AnyMessage]):
        for m in messages:
            if m.id is None:
                m.id = str(uuid.uuid4())

    def _should_summarize(self, messages: list[AnyMessage]) -> bool:
        return len(messages) > self.max_messages

    def _cutoff(self, messages: list[AnyMessage]) -> int:
        return len(messages) - self.keep_messages

    def _format(self, messages: list[AnyMessage]) -> str:
        return "\n".join(
            f"{'user' if m.type == 'human' else m.type}: {m.content}"
            for m in messages
        )

    def before_model(
        self, state: AgentState[Any], runtime: Runtime[Any]
    ) -> Optional[dict[str, Any]]:
        messages = state["messages"]
        self._ensure_ids(messages)
        if not self._should_summarize(messages):
            return None
        cutoff = self._cutoff(messages)
        summary = self._summarize(messages[:cutoff])
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                SystemMessage(content=f"Previous conversation summary:\n\n{summary}"),
                *messages[cutoff:],
            ]
        }

    async def abefore_model(
        self, state: AgentState[Any], runtime: Runtime[Any]
    ) -> Optional[dict[str, Any]]:
        messages = state["messages"]
        self._ensure_ids(messages)
        if not self._should_summarize(messages):
            return None
        cutoff = self._cutoff(messages)
        summary = await self._asummarize(messages[:cutoff])
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                SystemMessage(content=f"Previous conversation summary:\n\n{summary}"),
                *messages[cutoff:],
            ]
        }

    def _summarize(self, messages: list[AnyMessage]) -> str:
        if not messages:
            return "No prior conversation."
        response = self.model.invoke(self.prompt.format(messages=self._format(messages)))
        return response.text.strip()

    async def _asummarize(self, messages: list[AnyMessage]) -> str:
        if not messages:
            return "No prior conversation."
        response = await self.model.ainvoke(
            self.prompt.format(messages=self._format(messages))
        )
        return response.text.strip()
