from datetime import datetime, timezone
from typing import Any, Optional

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState
from langchain_core.messages import SystemMessage


class DateTimeMiddleware(AgentMiddleware):
    """AgentMiddleware that injects current server date/time and optional client timezone.

    Uses the `abefore_agent` hook to add a SystemMessage with current datetime
    information before each agent invocation. This runs once per agent call,
    ensuring the time context is always current.

    The middleware supports an optional timezone name (e.g. "Europe/Moscow",
    "America/New_York") for displaying the user's local time. If not provided,
    only UTC and server local time are shown.

    Example:
        ```python
        from middleware import DateTimeMiddleware

        middleware = DateTimeMiddleware(timezone_name="Europe/Moscow")
        agent = create_agent(
            model=model,
            tools=tools,
            middleware=[middleware],
        )
        ```
    """

    def __init__(self, timezone_name: Optional[str] = None):
        self._timezone_name = timezone_name

    async def abefore_agent(
        self, state: AgentState[Any], runtime: Any
    ) -> dict[str, Any] | None:
        now_utc = datetime.now(timezone.utc)
        now_local = datetime.now().astimezone()

        content = _build_time_context(now_utc, now_local, self._timezone_name)
        return {"messages": [SystemMessage(content=content)]}

    def before_agent(
        self, state: AgentState[Any], runtime: Any
    ) -> dict[str, Any] | None:
        now_utc = datetime.now(timezone.utc)
        now_local = datetime.now().astimezone()
        content = _build_time_context(now_utc, now_local, self._timezone_name)
        return {"messages": [SystemMessage(content=content)]}


def _build_time_context(
    now_utc: datetime, now_local: datetime, timezone_name: str | None = None
) -> str:
    lines = [
        "Current date and time (internal context):",
        f"  UTC:  {now_utc.strftime('%A, %Y-%m-%d %H:%M:%S')} UTC",
        f"  Server: {now_local.strftime('%A, %Y-%m-%d %H:%M:%S %z')}",
    ]
    if timezone_name:
        lines.append(f"  User timezone: {timezone_name}")
    lines.append("")
    lines.append("Do NOT mention or announce the current date or time to the user unless they explicitly ask about it.")
    lines.append("Use this context internally for tool calls and queries that need date/time information.")
    return "\n".join(lines)
