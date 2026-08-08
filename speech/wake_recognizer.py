"""Reconocimiento rápido y local de la palabra de activación."""

from __future__ import annotations

import json
import wave
from pathlib import Path


class WakeRecognitionError(RuntimeError):
    pass


class VoskWakeRecognizer:
    def __init__(self, model_path: Path) -> None:
        try:
            from vosk import Model, SetLogLevel

            SetLogLevel(-1)
            self.model = Model(str(model_path))
        except (ImportError, OSError, RuntimeError) as error:
            raise WakeRecognitionError("Vosk no está disponible.") from error

    def transcribe(self, audio: Path) -> str:
        try:
            from vosk import KaldiRecognizer

            with wave.open(str(audio), "rb") as recording:
                grammar = json.dumps(
                    ["odin", "odín", "olín", "odim", "[unk]"],
                    ensure_ascii=False,
                )
                recognizer = KaldiRecognizer(
                    self.model, recording.getframerate(), grammar
                )
                recognizer.AcceptWaveform(
                    recording.readframes(recording.getnframes())
                )
                result = json.loads(recognizer.FinalResult())
        except (OSError, RuntimeError, ValueError, wave.Error) as error:
            raise WakeRecognitionError("Vosk no pudo reconocer la activación.") from error
        return str(result.get("text", "")).strip()
