"""Grabación de micrófono en WAV compatible con whisper.cpp."""

from __future__ import annotations

import wave
from pathlib import Path

import sounddevice as sd


class MicrophoneError(RuntimeError):
    pass


class MicrophoneRecorder:
    def __init__(self, sample_rate: int = 16_000, device: int | str | None = None) -> None:
        self.sample_rate = sample_rate
        self.device = device

    def record_for(self, output: Path, seconds: float = 7.0) -> Path:
        if seconds <= 0:
            raise ValueError("La duración debe ser mayor que cero.")
        chunks: list[bytes] = []

        def capture(indata, frames, time_info, status) -> None:
            del frames, time_info
            if status:
                raise MicrophoneError(f"Error de captura de audio: {status}")
            chunks.append(bytes(indata))

        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                device=self.device,
                callback=capture,
            ):
                sd.sleep(round(seconds * 1000))
        except Exception as error:
            raise MicrophoneError(f"No se pudo grabar desde el micrófono: {error}") from error

        output.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(b"".join(chunks))
        return output
