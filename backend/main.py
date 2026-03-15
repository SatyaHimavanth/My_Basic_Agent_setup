from __future__ import annotations

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic import Field

from agents.basic_agent.service import get_basic_agent_service


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ReviewRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    edited_args: dict | None = None
    reject_message: str | None = None


app = FastAPI(title="Basic HITL Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict:
    try:
        return get_basic_agent_service().chat(
            thread_id=request.thread_id,
            message=request.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/review")
def review(request: ReviewRequest) -> dict:
    try:
        return get_basic_agent_service().review(
            thread_id=request.thread_id,
            decision=request.decision,
            edited_args=request.edited_args,
            reject_message=request.reject_message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
