from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware import AgentState
from langchain.agents.middleware import hook_config
from langchain.messages import AIMessage
from langgraph.runtime import Runtime

from agents.utils.llms import get_llm
from agents.utils.logging import get_logger


logger = get_logger(__name__)


class SafetyGuardrailMiddleware(AgentMiddleware):
    """Model-based guardrail that blocks unsafe final responses."""

    def __init__(self, safety_model=None):
        super().__init__()
        self.safety_model = safety_model or get_llm()

    @hook_config(can_jump_to=["end"])
    def after_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        if not state["messages"]:
            return None

        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage):
            return None

        safety_prompt = (
            "Evaluate whether this response is safe and appropriate. "
            "Reply with only SAFE or UNSAFE.\n\n"
            f"Response:\n{last_message.content}"
        )

        result = self.safety_model.invoke([{"role": "user", "content": safety_prompt}])
        decision = getattr(result, "content", "")

        if "UNSAFE" in str(decision).upper():
            logger.warning("Safety guardrail replaced an unsafe response.")
            last_message.content = "I cannot provide that response. Please rephrase your request."

        return None
