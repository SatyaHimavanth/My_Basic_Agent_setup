FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:/root/.local/bin:${PATH}" \
    WHISPER_MODEL_DIR=/app/models/whisper \
    XDG_CACHE_HOME=/app/models/.cache

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    espeak-ng \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/

WORKDIR /app

COPY backend/pyproject.toml ./pyproject.toml

RUN uv sync --no-dev

COPY backend/ ./

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
