from __future__ import annotations

from collections.abc import Iterable

from deepagents.backends import FilesystemBackend
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.subagents import SubAgentMiddleware
from langchain.agents.middleware import ClearToolUsesEdit
from langchain.agents.middleware import ContextEditingMiddleware
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain.agents.middleware import ModelRetryMiddleware
from langchain.agents.middleware import PIIMiddleware
from langchain.agents.middleware import SummarizationMiddleware
from langchain.agents.middleware import TodoListMiddleware
from langchain.agents.middleware import ToolRetryMiddleware

from agents.core.config import MiddlewareSettings
from agents.core.guardrails import SafetyGuardrailMiddleware


class InputEmailRedactionMiddleware(PIIMiddleware):
    @property
    def name(self) -> str:
        return "PIIMiddleware[email_input_redact]"


class OutputEmailHashMiddleware(PIIMiddleware):
    @property
    def name(self) -> str:
        return "PIIMiddleware[email_output_hash]"


def build_default_middleware(
    *,
    primary_model,
    fallback_model,
    settings: MiddlewareSettings,
) -> list:
    middleware = [
        ModelRetryMiddleware(
            max_retries=settings.model_retry_max_retries,
            backoff_factor=settings.retry_backoff_factor,
            initial_delay=settings.retry_initial_delay,
        ),
        ToolRetryMiddleware(
            max_retries=settings.tool_retry_max_retries,
            backoff_factor=settings.retry_backoff_factor,
            initial_delay=settings.retry_initial_delay,
        ),
        ModelFallbackMiddleware(fallback_model),
        ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=settings.context_edit_trigger_tokens,
                    keep=settings.context_edit_keep_tool_uses,
                ),
            ],
        ),
        SummarizationMiddleware(
            model=primary_model,
            trigger=("tokens", settings.summarization_trigger_tokens),
            keep=("messages", settings.summarization_keep_messages),
        ),
        InputEmailRedactionMiddleware("email", strategy="redact", apply_to_input=True),
        OutputEmailHashMiddleware("email", strategy="hash", apply_to_output=True),
        SafetyGuardrailMiddleware(primary_model),
    ]

    if settings.enable_todo_middleware:
        middleware.append(TodoListMiddleware())

    return middleware


def build_filesystem_middleware(*, root_dir, system_prompt: str) -> FilesystemMiddleware:
    return FilesystemMiddleware(
        backend=FilesystemBackend(root_dir=str(root_dir), virtual_mode=True),
        system_prompt=system_prompt,
    )


def build_subagent_middleware(*, root_dir, subagents: Iterable[dict]) -> SubAgentMiddleware:
    return SubAgentMiddleware(
        backend=FilesystemBackend(root_dir=str(root_dir), virtual_mode=True),
        subagents=list(subagents),
    )
