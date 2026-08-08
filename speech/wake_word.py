"""Escucha local de la palabra de activación ODIN."""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Callable

from speech.recorder import MicrophoneError, MicrophoneRecorder
from speech.whisper import TranscriptionError, WhisperTranscriber


def interpret_wake_phrase(
    text: str, *, forced: bool = False, waiting_for_question: bool = False
) -> tuple[str | None, bool]:
    # Whisper Base confundía a veces ODIN con "Olín"; ambas formas son
    # acústicamente cercanas y sólo activan una orden completa.
    match = re.search(
        r"\b(?:od[ií]n|ol[ií]n|odim|odyn)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not (forced or waiting_for_question or match):
        return None, waiting_for_question
    question = text.strip()
    if match:
        question = (text[:match.start()] + " " + text[match.end():]).strip(" ,.:;-")
    if not question:
        return None, True
    return question, False


class WakeWordListener:
    def __init__(
        self,
        data_root: Path,
        on_question: Callable[[str], None],
        recorder: MicrophoneRecorder | None = None,
        transcriber: WhisperTranscriber | None = None,
    ) -> None:
        self.audio_path = data_root / "speech" / "wake_command.wav"
        self.on_question = on_question
        self.recorder = recorder or MicrophoneRecorder()
        self.transcriber = transcriber or WhisperTranscriber()
        self.stop_event = threading.Event()
        self.armed = threading.Event()
        self.paused = threading.Event()

    def arm(self) -> None:
        """F8 hace que la siguiente frase sea una consulta sin exigir 'ODIN'."""

        self.armed.set()

    def run(self) -> None:
        waiting_for_question = False
        while not self.stop_event.is_set():
            if self.paused.is_set():
                self.stop_event.wait(0.1)
                continue
            try:
                audio = self.recorder.record_utterance(
                    self.audio_path, silence_seconds=1.0, stop_event=self.stop_event
                )
                if audio is None:
                    continue
                text = self.transcriber.transcribe(audio).strip()
            except (MicrophoneError, TranscriptionError):
                continue

            forced = self.armed.is_set()
            self.armed.clear()
            question, waiting_for_question = interpret_wake_phrase(
                text, forced=forced, waiting_for_question=waiting_for_question
            )
            if question is None:
                continue
            self.paused.set()
            self.on_question(question)

    def stop(self) -> None:
        self.stop_event.set()

    def resume(self) -> None:
        self.paused.clear()
