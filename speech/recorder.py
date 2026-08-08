"""Grabación de micrófono en WAV compatible con whisper.cpp."""

from __future__ import annotations

import wave
import queue
import time
from array import array
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

    def record_utterance(
        self,
        output: Path,
        *,
        silence_seconds: float = 1.0,
        max_seconds: float = 20.0,
        stop_event=None,
    ) -> Path | None:
        """Espera voz y termina tras un segundo de silencio."""

        chunks: list[bytes] = []
        incoming: queue.Queue[bytes] = queue.Queue()
        speech_started = False
        speech_at = 0.0
        started_at = time.monotonic()

        def capture(indata, frames, time_info, status) -> None:
            del frames, time_info
            if not status:
                incoming.put(bytes(indata))

        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=1600,
                channels=1,
                dtype="int16",
                device=self.device,
                callback=capture,
            ):
                while time.monotonic() - started_at < max_seconds:
                    if stop_event is not None and stop_event.is_set():
                        return None
                    try:
                        chunk = incoming.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    samples = array("h")
                    samples.frombytes(chunk)
                    rms = (
                        (sum(sample * sample for sample in samples) / len(samples)) ** 0.5
                        if samples else 0
                    )
                    now = time.monotonic()
                    if rms >= 350:
                        speech_started = True
                        speech_at = now
                    if speech_started:
                        chunks.append(chunk)
                        if now - speech_at >= silence_seconds:
                            break
        except Exception as error:
            raise MicrophoneError(f"No se pudo escuchar el micrófono: {error}") from error

        if not chunks:
            return None
        output.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(b"".join(chunks))
        return output
