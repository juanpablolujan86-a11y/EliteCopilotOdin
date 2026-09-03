"""Selección y recuperación automática del reconocimiento de órdenes."""

from __future__ import annotations

from pathlib import Path

from core.config import Config
from speech.faster_whisper import FasterWhisperTranscriber
from speech.parakeet import ParakeetTranscriber
from speech.whisper import TranscriptionError, WhisperTranscriber


class FallbackTranscriber:
    def __init__(self, primary, fallback) -> None:
        self.primary = primary
        self.fallback = fallback

    def warm_up(self) -> bool:
        warm_up = getattr(self.primary, "warm_up", None)
        return bool(warm_up and warm_up())

    def transcribe(self, audio: Path) -> str:
        try:
            return self.primary.transcribe(audio)
        except (TranscriptionError, OSError, RuntimeError):
            return self.fallback.transcribe(audio)

    def transcribe_with_confidence(self, audio: Path) -> tuple[str, float]:
        try:
            return self.primary.transcribe_with_confidence(audio)
        except (TranscriptionError, OSError, RuntimeError):
            return self.fallback.transcribe_with_confidence(audio)


def create_command_transcriber(config: Config | None = None):
    config = config or Config()
    whisper = FasterWhisperTranscriber(
        config=config,
        fallback=WhisperTranscriber(model_preference="small", threads=4),
    )
    provider = config.speech_recognition_provider
    if provider == "whisper":
        return whisper
    parakeet = ParakeetTranscriber(config.parakeet_model_root)
    if provider == "parakeet" or parakeet.available:
        return FallbackTranscriber(parakeet, whisper)
    return whisper

