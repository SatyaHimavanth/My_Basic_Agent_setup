from __future__ import annotations

import os

from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings

from agents.utils.logging import get_logger


logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_llm():
    logger.info("Initializing primary chat model.")
    return init_chat_model(
        model=os.getenv("CHAT_MODEL", ""),
        azure_deployment=os.getenv("CHAT_DEPLOYMENT_NAME", ""),
    )


@lru_cache(maxsize=1)
def get_fallback_llm():
    logger.info("Initializing fallback chat model.")
    return init_chat_model(
        model=os.getenv("FALLBACK_CHAT_MODEL", "llama3.2"),
        model_provider=os.getenv("FALLBACK_MODEL_PROVIDER", "ollama"),
    )


@lru_cache(maxsize=1)
def get_embedding():
    logger.info("Initializing embedding model.")
    return init_embeddings(
        model=os.getenv("EMBEDDING_MODEL", ""),
        azure_deployment=os.getenv("EMBEDDING_DEPLOYMENT_NAME", ""),
    )
