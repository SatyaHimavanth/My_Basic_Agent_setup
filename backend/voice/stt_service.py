from __future__ import annotations

import io
import os
import time
import wave

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

from agents.utils.logging import get_logger


logger = get_logger(__name__)


def _default_whisper_model_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "models" / "whisper"


@dataclass(slots=True)
class STTRuntimeInfo:
    available: bool
    reason: str | None = None
    device: str | None = None
    precision: str | None = None
    model_size: str | None = None


def _detect_compute_runtime() -> tuple[str, bool, str]:
    if not find_spec("torch"):
        return "cpu", False, "fp32"

    import torch

    if torch.cuda.is_available():
        return "cuda", True, "fp16"

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps", False, "fp32"

    return "cpu", False, "fp32"


class STTService:
    def __init__(self) -> None:
        self.model = None
        self.device = None
        self.use_fp16 = False
        self.precision = None
        self.model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
        configured_dir = os.getenv("WHISPER_MODEL_DIR")
        self.model_dir = Path(configured_dir) if configured_dir else _default_whisper_model_dir()
        self._initialization_error: str | None = None

    def get_runtime_info(self) -> STTRuntimeInfo:
        if self.model is not None:
            return STTRuntimeInfo(
                available=True,
                device=self.device,
                precision=self.precision,
                model_size=self.model_size,
            )

        if not find_spec("whisper"):
            return STTRuntimeInfo(
                available=False,
                reason="The 'openai-whisper' package is not installed. Run `uv sync` in backend to enable server STT.",
                model_size=self.model_size,
            )

        if not find_spec("numpy"):
            return STTRuntimeInfo(
                available=False,
                reason="The 'numpy' package is not installed. Run `uv sync` in backend to enable server STT.",
                model_size=self.model_size,
            )

        device, _, precision = _detect_compute_runtime()
        return STTRuntimeInfo(
            available=True,
            device=device,
            precision=precision,
            model_size=self.model_size,
        )

    def transcribe_wav(self, wav_data: bytes) -> str:
        if not self._ensure_model():
            raise RuntimeError(self._initialization_error or "STT service unavailable.")

        try:
            import numpy as np

            with io.BytesIO(wav_data) as buffer:
                with wave.open(buffer, "rb") as wav_file:
                    frames = wav_file.readframes(wav_file.getnframes())
            audio_array = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            result = self.model.transcribe(
                audio_array,
                language="en",
                fp16=self.use_fp16,
            )
            return str(result.get("text", "")).strip()
        except Exception as exc:
            logger.exception("Server-side transcription failed.")
            raise RuntimeError(f"STT transcription failed: {exc}") from exc

    def _ensure_model(self) -> bool:
        if self.model is not None:
            return True

        if self._initialization_error is not None:
            return False

        if not find_spec("whisper"):
            self._initialization_error = (
                "The 'openai-whisper' package is not installed. Run `uv sync` in backend to enable server STT."
            )
            return False

        if not find_spec("numpy"):
            self._initialization_error = (
                "The 'numpy' package is not installed. Run `uv sync` in backend to enable server STT."
            )
            return False

        try:
            import whisper

            self.device, self.use_fp16, self.precision = _detect_compute_runtime()
            self.model_dir.mkdir(parents=True, exist_ok=True)
            model_exists = self._model_file_path().exists()
            max_attempts = 3 if not model_exists else 1

            for attempt in range(1, max_attempts + 1):
                try:
                    if not model_exists:
                        logger.info(
                            "Whisper model '%s' not found in %s. Download attempt %s/%s.",
                            self.model_size,
                            self.model_dir,
                            attempt,
                            max_attempts,
                        )

                    self.model = whisper.load_model(
                        self.model_size,
                        download_root=str(self.model_dir),
                        device=self.device,
                    )
                    logger.info(
                        "Loaded Whisper model '%s' on %s with %s precision from %s.",
                        self.model_size,
                        self.device,
                        self.precision,
                        self.model_dir,
                    )
                    return True
                except Exception as exc:
                    if attempt >= max_attempts:
                        raise

                    logger.warning(
                        "Whisper model download attempt %s/%s failed: %s",
                        attempt,
                        max_attempts,
                        exc,
                    )
                    time.sleep(1)
        except Exception as exc:
            self._initialization_error = f"Failed to initialize Whisper: {exc}"
            logger.exception("Failed to initialize server-side STT.")
            return False

    def _model_file_path(self) -> Path:
        return self.model_dir / f"{self.model_size}.pt"


_stt_service: STTService | None = None


def get_stt_service() -> STTService:
    global _stt_service
    if _stt_service is None:
        _stt_service = STTService()
    return _stt_service
