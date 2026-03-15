from __future__ import annotations

import logging

from datetime import datetime
from pathlib import Path

from agents.core.config import get_runtime_settings


_LOGGER_CONFIGURED = False


def _build_log_file_path() -> Path:
    settings = get_runtime_settings()
    settings.paths.logs_dir.mkdir(parents=True, exist_ok=True)
    date_stamp = datetime.now().strftime("%Y-%m-%d")
    return settings.paths.logs_dir / f"agents-{date_stamp}.log"


def configure_logging(level: int = logging.INFO) -> None:
    global _LOGGER_CONFIGURED

    if _LOGGER_CONFIGURED:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(_build_log_file_path(), encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
    else:
        has_daily_file = any(
            isinstance(handler, logging.FileHandler)
            and Path(getattr(handler, "baseFilename", "")) == _build_log_file_path()
            for handler in root_logger.handlers
        )
        if not has_daily_file:
            root_logger.addHandler(file_handler)

    _LOGGER_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
