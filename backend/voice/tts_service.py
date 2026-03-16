from __future__ import annotations

import base64
import os
import tempfile

from contextlib import contextmanager
from dataclasses import dataclass
from importlib.util import find_spec

from agents.utils.logging import get_logger


logger = get_logger(__name__)


@dataclass(slots=True)
class TTSRuntimeInfo:
    available: bool
    reason: str | None = None


class TTSService:
    def __init__(self) -> None:
        self._initialization_error: str | None = None

    def get_runtime_info(self) -> TTSRuntimeInfo:
        if not find_spec("pyttsx3"):
            return TTSRuntimeInfo(
                available=False,
                reason="The 'pyttsx3' package is not installed. Run `uv sync` in backend to enable server TTS.",
            )

        return TTSRuntimeInfo(available=True)

    def list_voices(self) -> list[dict[str, str]]:
        try:
            with self._engine_session() as engine:
                voices = engine.getProperty("voices") or []
                return [
                    {
                        "id": voice.id,
                        "name": voice.name,
                        "languages": ",".join(
                            language.decode("utf-8", errors="ignore")
                            if isinstance(language, bytes)
                            else str(language)
                            for language in (voice.languages or [])
                        ),
                    }
                    for voice in voices
                ]
        except RuntimeError:
            return []

    def get_current_voice(self) -> str | None:
        try:
            with self._engine_session() as engine:
                return engine.getProperty("voice")
        except RuntimeError:
            return None

    def speak_to_base64_with_settings(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        rate: int | None = None,
    ) -> str | None:
        audio_data = self._speak_with_settings(text, voice_id=voice_id, rate=rate)
        if audio_data is None:
            return None
        return base64.b64encode(audio_data).decode("utf-8")

    def _speak_with_settings(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        rate: int | None = None,
    ) -> bytes | None:
        with self._engine_session() as engine:
            if voice_id:
                engine.setProperty("voice", voice_id)
            if rate is not None:
                engine.setProperty("rate", rate)
            return self._speak(text, engine)

    def _speak(self, text: str, engine) -> bytes | None:
        if not text.strip():
            return None

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_path = temp_file.name

            engine.save_to_file(text, temp_path)
            engine.runAndWait()

            with open(temp_path, "rb") as output_file:
                return output_file.read()
        except Exception as exc:
            logger.exception("Server-side TTS failed.")
            raise RuntimeError(f"TTS synthesis failed: {exc}") from exc
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    logger.warning("Unable to remove temporary TTS file: %s", temp_path)

    @contextmanager
    def _engine_session(self):
        if not find_spec("pyttsx3"):
            reason = (
                "The 'pyttsx3' package is not installed. Run `uv sync` in backend to enable server TTS."
            )
            self._initialization_error = reason
            raise RuntimeError(reason)

        comtypes_module = None
        try:
            if find_spec("comtypes"):
                import comtypes

                comtypes_module = comtypes
                comtypes.CoInitialize()

            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            for voice in voices:
                if "english" in voice.name.lower():
                    engine.setProperty("voice", voice.id)
                    break
            engine.setProperty("rate", 170)
            engine.setProperty("volume", 1.0)
            yield engine
        except Exception as exc:
            self._initialization_error = f"Failed to initialize pyttsx3: {exc}"
            logger.exception("Failed to initialize server-side TTS.")
            raise RuntimeError(self._initialization_error) from exc
        finally:
            if comtypes_module is not None:
                try:
                    comtypes_module.CoUninitialize()
                except Exception:
                    logger.debug("COM uninitialization skipped.", exc_info=True)


_tts_service: TTSService | None = None


def get_tts_service() -> TTSService:
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service
