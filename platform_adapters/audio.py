"""Selección de reproducción de audio y síntesis local por plataforma."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class AudioPlayer(Protocol):
    def play(self, audio: bytes) -> None: ...


@runtime_checkable
class SpeechPlayer(Protocol):
    def speak(self, text: str, voice: str = "", rate: int = 0, volume: int = 100) -> None: ...


class AudioAdapterUnavailable(RuntimeError):
    pass


def _require_windows() -> None:
    system = platform.system()
    if system != "Windows":
        raise AudioAdapterUnavailable(
            f"ODIN todavía no dispone de reproducción de voz para {system or 'este sistema'}."
        )


def create_audio_player(cache_directory: Path | None = None) -> AudioPlayer:
    _require_windows()
    from voice.playback import WindowsMp3Player

    return WindowsMp3Player(cache_directory)


def create_speech_player() -> SpeechPlayer:
    _require_windows()
    from voice.playback import WindowsSpeechPlayer

    return WindowsSpeechPlayer()
