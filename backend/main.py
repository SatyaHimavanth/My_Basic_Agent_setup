from __future__ import annotations

import json

from collections.abc import Iterable
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic import Field
from starlette.responses import StreamingResponse

from agents.basic_agent.service import get_basic_agent_service
from voice.stt_service import get_stt_service
from voice.tts_service import get_tts_service


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ReviewRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    edited_args: dict | None = None
    reject_message: str | None = None


class TTSRequest(BaseModel):
    text: str
    voice_id: str | None = None
    speed: float = 1.0


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


def _stream_as_ndjson(events: Iterable[dict]) -> StreamingResponse:
    def generate():
        for event in events:
            yield json.dumps(event) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.get("/api/voice/capabilities")
def voice_capabilities() -> dict:
    stt_service = get_stt_service()
    tts_service = get_tts_service()
    stt_runtime = stt_service.get_runtime_info()
    tts_runtime = tts_service.get_runtime_info()
    tts_voices = []
    default_voice_id = None

    if tts_runtime.available:
        try:
            tts_voices = tts_service.list_voices()
            default_voice_id = tts_service.get_current_voice()
        except Exception:
            tts_voices = []
            default_voice_id = None
            tts_runtime.reason = "Server TTS is installed but failed to initialize."
            tts_runtime.available = False

    return {
        "stt": {
            "available": stt_runtime.available,
            "reason": stt_runtime.reason,
            "device": stt_runtime.device,
            "precision": stt_runtime.precision,
            "model_size": stt_runtime.model_size,
        },
        "tts": {
            "available": tts_runtime.available,
            "reason": tts_runtime.reason,
            "voices": tts_voices,
            "default_voice_id": default_voice_id,
        },
    }


@app.post("/api/voice/stt")
async def voice_stt(request: Request) -> dict:
    wav_data = await request.body()
    if not wav_data:
        raise HTTPException(status_code=400, detail="Audio payload is empty.")

    runtime = get_stt_service().get_runtime_info()
    if not runtime.available:
        raise HTTPException(status_code=503, detail=runtime.reason or "Server STT unavailable.")

    try:
        transcript = get_stt_service().transcribe_wav(wav_data)
        return {"text": transcript}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/voice/tts")
def voice_tts(request: TTSRequest) -> dict:
    runtime = get_tts_service().get_runtime_info()
    if not runtime.available:
        raise HTTPException(status_code=503, detail=runtime.reason or "Server TTS unavailable.")

    text = request.text.strip()
    if not text:
        return {"audio": None}

    rate = max(80, min(260, int(170 * request.speed)))
    try:
        audio = get_tts_service().speak_to_base64_with_settings(
            text,
            voice_id=request.voice_id,
            rate=rate,
        )
        return {"audio": audio}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    try:
        events = get_basic_agent_service().stream_chat(
            thread_id=request.thread_id,
            message=request.message,
        )
        return _stream_as_ndjson(events)
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


@app.post("/api/review/stream")
def review_stream(request: ReviewRequest) -> StreamingResponse:
    try:
        events = get_basic_agent_service().stream_review(
            thread_id=request.thread_id,
            decision=request.decision,
            edited_args=request.edited_args,
            reject_message=request.reject_message,
        )
        return _stream_as_ndjson(events)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
