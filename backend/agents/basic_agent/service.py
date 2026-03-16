from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator
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


def _extract_text_from_message(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(part for part in parts if part).strip()
    return ""


def _tool_preview(tool_message: Any) -> str:
    content = _extract_text_from_message(tool_message)
    if not content:
        return "Tool completed."
    if len(content) <= 140:
        return content
    return f"{content[:137].rstrip()}..."


class BasicAgentService:
    def __init__(self) -> None:
        self._agent = create_basic_agent()
        self._pending_by_thread: dict[str, PendingReview] = {}

    def chat(self, *, thread_id: str, message: str) -> dict[str, Any]:
        return self._consume_terminal_event(self.stream_chat(thread_id=thread_id, message=message))

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
        return self._consume_terminal_event(
            self._stream_result(
                thread_id=thread_id,
                agent_input=Command(resume={"decisions": [resume_payload]}),
                approval_tool_name=pending.tool_name,
            )
        )

    def stream_chat(self, *, thread_id: str, message: str) -> Iterator[dict[str, Any]]:
        yield from self._stream_result(
            thread_id=thread_id,
            agent_input={"messages": [{"role": "user", "content": message}]},
        )

    def stream_review(
        self,
        *,
        thread_id: str,
        decision: str,
        edited_args: dict[str, Any] | None = None,
        reject_message: str | None = None,
    ) -> Iterator[dict[str, Any]]:
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
        yield from self._stream_result(
            thread_id=thread_id,
            agent_input=Command(resume={"decisions": [resume_payload]}),
            approval_tool_name=pending.tool_name,
        )

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

    def _stream_result(
        self,
        *,
        thread_id: str,
        agent_input: Any,
        approval_tool_name: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        config = {"configurable": {"thread_id": thread_id}}
        seen_statuses: set[tuple[str, str]] = set()

        if approval_tool_name:
            status = self._build_status_event(
                stage="approval",
                text=f"Resuming {approval_tool_name} after review.",
            )
            seen_statuses.add((status["stage"], status["text"]))
            yield status

        for chunk in self._agent.stream(agent_input, config=config, stream_mode="updates"):
            for event in self._chunk_to_events(thread_id=thread_id, chunk=chunk):
                if event.get("type") == "status":
                    fingerprint = (str(event.get("stage", "")), str(event.get("text", "")))
                    if fingerprint in seen_statuses:
                        continue
                    seen_statuses.add(fingerprint)
                yield event

    def _chunk_to_events(self, *, thread_id: str, chunk: dict[str, Any]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        for node_name, payload in chunk.items():
            if node_name == "__interrupt__":
                interrupt_items = payload if isinstance(payload, (list, tuple)) else [payload]
                if interrupt_items:
                    pending = self._parse_interrupt(interrupt_items[0])
                    self._pending_by_thread[thread_id] = pending
                    events.append(
                        self._build_status_event(
                            stage="approval",
                            text=f"Waiting for approval to run {pending.tool_name}.",
                        )
                    )
                    events.append(
                        {
                            "type": "review_required",
                            "thread_id": thread_id,
                            "review": {
                                "tool_name": pending.tool_name,
                                "args": pending.args,
                                "allowed_decisions": pending.allowed_decisions,
                                "description": pending.description,
                            },
                        }
                    )
                continue

            if node_name == "model":
                events.extend(self._events_from_model_payload(payload))
                continue

            if node_name == "tools":
                events.extend(self._events_from_tool_payload(payload))
                continue

            status_text = self._middleware_status_text(node_name, payload)
            if status_text:
                events.append(self._build_status_event(stage="middleware", text=status_text))

        return events

    def _events_from_model_payload(self, payload: Any) -> list[dict[str, Any]]:
        data = _as_dict(payload)
        messages = data.get("messages", [])
        if not messages:
            return []

        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", []) or []
        events: list[dict[str, Any]] = []

        if tool_calls:
            events.append(self._build_status_event(stage="model", text="Planning next steps."))
            for tool_call in tool_calls:
                tool_name = str(tool_call.get("name", "tool"))
                tool_args = tool_call.get("args", {})
                detail = ""
                if isinstance(tool_args, dict) and tool_args:
                    preview = ", ".join(f"{key}={value}" for key, value in tool_args.items())
                    detail = f" ({preview})"
                events.append(
                    self._build_status_event(
                        stage="tool_call",
                        text=f"Calling {tool_name}{detail}.",
                    )
                )
            return events

        assistant_text = _extract_text_from_message(last_message)
        if assistant_text:
            events.append(
                {
                    "type": "assistant",
                    "message": assistant_text,
                }
            )
        return events

    def _events_from_tool_payload(self, payload: Any) -> list[dict[str, Any]]:
        data = _as_dict(payload)
        messages = data.get("messages", [])
        events: list[dict[str, Any]] = []
        for tool_message in messages:
            tool_name = getattr(tool_message, "name", "tool")
            preview = _tool_preview(tool_message)
            events.append(
                self._build_status_event(
                    stage="tool_result",
                    text=f"{tool_name} finished.",
                    detail=preview,
                )
            )
        return events

    def _middleware_status_text(self, node_name: str, payload: Any) -> str | None:
        if node_name == "SummarizationMiddleware.before_model":
            return "Updating conversation context."
        if node_name == "PIIMiddleware[email_input_redact].before_model":
            return "Checking your message for sensitive data."
        if node_name == "PIIMiddleware[email_output_hash].before_model":
            return "Applying privacy rules before response generation."
        if node_name == "PIIMiddleware[email_input_redact].after_model":
            return "Checking the draft response for sensitive data."
        if node_name == "PIIMiddleware[email_output_hash].after_model":
            return "Applying privacy rules to the response."
        if node_name == "TodoListMiddleware.after_model":
            return "Updating internal task tracking."
        if node_name == "HumanInTheLoopMiddleware.after_model":
            return None
        if node_name == "SafetyGuardrailMiddleware.after_agent":
            return "Running final safety checks."

        return None

    def _build_status_event(self, *, stage: str, text: str, detail: str | None = None) -> dict[str, Any]:
        event = {
            "type": "status",
            "stage": stage,
            "text": text,
        }
        if detail:
            event["detail"] = detail
        return event

    def _consume_terminal_event(self, events: Iterator[dict[str, Any]]) -> dict[str, Any]:
        terminal_event: dict[str, Any] | None = None
        for event in events:
            if event.get("type") in {"assistant", "review_required"}:
                terminal_event = event

        if terminal_event is None:
            raise RuntimeError("Agent stream completed without a terminal response.")
        return terminal_event


_service: BasicAgentService | None = None


def get_basic_agent_service() -> BasicAgentService:
    global _service
    if _service is None:
        _service = BasicAgentService()
    return _service
