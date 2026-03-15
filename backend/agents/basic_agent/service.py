from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.types import Command

from agents.basic_agent.agent import create_basic_agent


@dataclass
class PendingReview:
    tool_name: str
    args: dict[str, Any]
    allowed_decisions: list[str]
    description: str


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "dict"):
        dumped = value.dict()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "__dict__"):
        dumped = vars(value)
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _extract_assistant_text(result: dict[str, Any]) -> str:
    messages = result.get("messages", [])
    for message in reversed(messages):
        if getattr(message, "type", "") != "ai":
            continue
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            return "\n".join(part for part in parts if part).strip()
    return ""


class BasicAgentService:
    def __init__(self) -> None:
        self._agent = create_basic_agent()
        self._pending_by_thread: dict[str, PendingReview] = {}

    def chat(self, *, thread_id: str, message: str) -> dict[str, Any]:
        result = self._agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config={"configurable": {"thread_id": thread_id}},
        )
        return self._format_result(thread_id, result)

    def review(
        self,
        *,
        thread_id: str,
        decision: str,
        edited_args: dict[str, Any] | None = None,
        reject_message: str | None = None,
    ) -> dict[str, Any]:
        pending = self._pending_by_thread.get(thread_id)
        if pending is None:
            raise ValueError("No pending review found for this thread.")

        normalized_decision = decision.strip().lower()
        if normalized_decision not in pending.allowed_decisions:
            allowed = ", ".join(pending.allowed_decisions)
            raise ValueError(f"Decision '{normalized_decision}' not allowed. Allowed: {allowed}")

        if normalized_decision == "approve":
            resume_payload = {"type": "approve"}
        elif normalized_decision == "reject":
            resume_payload = {"type": "reject"}
            if reject_message:
                resume_payload["message"] = reject_message
        else:
            if not isinstance(edited_args, dict):
                raise ValueError("edited_args must be an object when decision is 'edit'.")
            resume_payload = {
                "type": "edit",
                "edited_action": {
                    "name": pending.tool_name,
                    "args": edited_args,
                },
            }

        del self._pending_by_thread[thread_id]
        result = self._agent.invoke(
            Command(resume={"decisions": [resume_payload]}),
            config={"configurable": {"thread_id": thread_id}},
        )
        return self._format_result(thread_id, result)

    def _format_result(self, thread_id: str, result: dict[str, Any]) -> dict[str, Any]:
        interrupts = result.get("__interrupt__", [])
        if interrupts:
            pending = self._parse_interrupt(interrupts[0])
            self._pending_by_thread[thread_id] = pending
            return {
                "type": "review_required",
                "thread_id": thread_id,
                "review": {
                    "tool_name": pending.tool_name,
                    "args": pending.args,
                    "allowed_decisions": pending.allowed_decisions,
                    "description": pending.description,
                },
            }

        return {
            "type": "assistant",
            "thread_id": thread_id,
            "message": _extract_assistant_text(result),
        }

    def _parse_interrupt(self, interrupt_obj: Any) -> PendingReview:
        payload = _as_dict(getattr(interrupt_obj, "value", interrupt_obj))
        action_requests = payload.get("action_requests", [])
        review_configs = payload.get("review_configs", [])
        if not action_requests or not review_configs:
            raise ValueError("Interrupt payload missing action request or review config.")

        action = _as_dict(action_requests[0])
        config = _as_dict(review_configs[0])
        raw_args = action.get("args")
        args = raw_args if isinstance(raw_args, dict) else {}

        return PendingReview(
            tool_name=str(action.get("name", "unknown_tool")),
            args=args,
            allowed_decisions=[str(item) for item in config.get("allowed_decisions", [])],
            description=str(action.get("description") or "Approval required."),
        )


_service: BasicAgentService | None = None


def get_basic_agent_service() -> BasicAgentService:
    global _service
    if _service is None:
        _service = BasicAgentService()
    return _service
