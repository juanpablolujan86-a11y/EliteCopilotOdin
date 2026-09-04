"""Escucha local de la palabra de activación ODIN."""

from __future__ import annotations

import re
import threading
import logging
import time
from numbers import Real
from pathlib import Path
from typing import Callable

from speech.recorder import MicrophoneError, MicrophoneRecorder
from speech.whisper import TranscriptionError, WhisperTranscriber
from speech.faster_whisper import FasterWhisperTranscriber
from speech.transcriber import create_command_transcriber
from speech.wake_recognizer import VoskWakeRecognizer, WakeRecognitionError


logger = logging.getLogger("odin.voice")


class _RecordingStopSignal:
    """Cancela una captura pasiva sin detener definitivamente el listener."""

    def __init__(self, listener: "WakeWordListener") -> None:
        self.listener = listener

    def is_set(self) -> bool:
        return self.listener.stop_event.is_set() or (
            self.listener._passive_cancelled.is_set()
            and not self.listener.armed.is_set()
        )


def interpret_wake_phrase(
    text: str, *, forced: bool = False, waiting_for_question: bool = False
) -> tuple[str | None, bool]:
    # Deformaciones observadas de la orden completa "ODIN, tren de
    # aterrizaje". Se aceptan sólo cuando la frase contiene también
    # "aterrizaje" para no convertir "o de..." en una palabra de activación
    # genérica y provocar escuchas accidentales.
    if re.fullmatch(
        r"\s*o\s+de\s+(?:(?:in|inter)\s*)?(?:tren[d]?|tres?)?\s*"
        r"(?:de\s+)?(?:aterrizaje|interrizaje)\s*[.,;:!?]*\s*",
        text,
        flags=re.IGNORECASE,
    ):
        return "tren de aterrizaje", False
    # Whisper Base confundía a veces ODIN con "Olín"; ambas formas son
    # acústicamente cercanas y sólo activan una orden completa.
    match = re.search(
        r"\b(?:od[ií]n|odi+n|ol[ií]n|odim|odyn)\b",
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
        on_activation: Callable[[], None] | None = None,
        on_unclear: Callable[[], None] | None = None,
        recorder: MicrophoneRecorder | None = None,
        transcriber: WhisperTranscriber | None = None,
        wake_transcriber: WhisperTranscriber | None = None,
    ) -> None:
        self.audio_path = data_root / "speech" / "wake_command.wav"
        self.on_question = on_question
        self.on_activation = on_activation or (lambda: None)
        self.on_unclear = on_unclear or (lambda: None)
        self.recorder = recorder or MicrophoneRecorder()
        command_silence = getattr(self.recorder, "command_silence_seconds", 1.0)
        self.command_silence_seconds = (
            float(command_silence) if isinstance(command_silence, Real) else 1.0
        )
        # La escucha permanente debe competir lo mínimo posible con el juego.
        # Base reconoce órdenes breves con mucha menos carga que Small; los
        # alias de interpret_wake_phrase cubren sus variantes de "ODIN".
        self.transcriber = transcriber or create_command_transcriber()
        if wake_transcriber is not None:
            self.wake_transcriber = wake_transcriber
        elif transcriber is not None:
            self.wake_transcriber = self.transcriber
        else:
            try:
                self.wake_transcriber = VoskWakeRecognizer(
                    data_root / "speech" / "models" / "vosk-model-small-es-0.42"
                )
            except WakeRecognitionError:
                self.wake_transcriber = self.transcriber
        logger.info(
            "VOICE_ENGINES | command=%s | wake=%s",
            type(self.transcriber).__name__, type(self.wake_transcriber).__name__,
        )
        self.stop_event = threading.Event()
        self.armed = threading.Event()
        self.paused = threading.Event()
        self.passive_enabled = threading.Event()
        self.passive_enabled.set()
        self._passive_cancelled = threading.Event()
        self._recording_stop_signal = _RecordingStopSignal(self)
        self._pause_condition = threading.Condition()

    def arm(self) -> None:
        """F8 hace que la siguiente frase sea una consulta sin exigir 'ODIN'."""

        self.armed.set()
        with self._pause_condition:
            self._pause_condition.notify_all()

    def enable_passive_listening(self, enabled: bool) -> None:
        if enabled:
            self.passive_enabled.set()
            self._passive_cancelled.clear()
        else:
            self.passive_enabled.clear()
            # record_utterance puede estar capturando cuando se guarda la
            # configuración. Esta señal interrumpe esa captura de inmediato.
            self._passive_cancelled.set()
        with self._pause_condition:
            self._pause_condition.notify_all()

    def run(self) -> None:
        waiting_for_question = False
        while not self.stop_event.is_set():
            with self._pause_condition:
                while (
                    (self.paused.is_set() or (
                        not self.passive_enabled.is_set() and not self.armed.is_set()
                    ))
                    and not self.stop_event.is_set()
                ):
                    self._pause_condition.wait()
            if self.stop_event.is_set():
                break
            try:
                audio = self.recorder.record_utterance(
                    self.audio_path,
                    silence_seconds=(
                        self.command_silence_seconds
                        if waiting_for_question or self.armed.is_set() else 0.65
                    ),
                    stop_event=self._recording_stop_signal,
                )
                if audio is None:
                    if not self.passive_enabled.is_set() and not self.armed.is_set():
                        waiting_for_question = False
                    continue
                recognizer = (
                    self.transcriber
                    if waiting_for_question or self.armed.is_set()
                    else self.wake_transcriber
                )
                transcription_started = time.perf_counter()
                if recognizer is self.transcriber:
                    text, confidence = recognizer.transcribe_with_confidence(audio)
                    if confidence < 0.35:
                        self.pause()
                        self.on_unclear()
                        continue
                else:
                    text = recognizer.transcribe(audio)
                text = text.strip()
                logger.info(
                    "VOICE_RECOGNIZED | mode=%s | engine=%s | seconds=%.3f | text=%r",
                    "command" if waiting_for_question or self.armed.is_set() else "wake",
                    type(recognizer).__name__,
                    time.perf_counter() - transcription_started,
                    text,
                )
            except (
                MicrophoneError, TranscriptionError, WakeRecognitionError,
                UnicodeError, OSError,
            ) as error:
                logger.warning(
                    "VOICE_RECOGNITION_FAILED | mode=%s | error=%s: %s",
                    "command" if waiting_for_question or self.armed.is_set() else "wake",
                    type(error).__name__, error,
                )
                # Si ODIN ya había confirmado que estaba escuchando, nunca debe
                # fallar en silencio: solicita repetir la orden y queda listo
                # para un nuevo intento.
                if waiting_for_question or self.armed.is_set():
                    waiting_for_question = False
                    self.armed.clear()
                    self.pause()
                    self.on_unclear()
                continue

            forced = self.armed.is_set()
            self.armed.clear()
            was_waiting = waiting_for_question
            question, waiting_for_question = interpret_wake_phrase(
                text, forced=forced, waiting_for_question=waiting_for_question
            )
            if question is None:
                if waiting_for_question and not was_waiting:
                    self.pause()
                    self.on_activation()
                continue
            self.pause()
            self.on_question(question)

    def stop(self) -> None:
        self.stop_event.set()
        with self._pause_condition:
            self._pause_condition.notify_all()

    def pause(self) -> None:
        with self._pause_condition:
            self.paused.set()

    def resume(self) -> None:
        with self._pause_condition:
            self.paused.clear()
            self._pause_condition.notify_all()
