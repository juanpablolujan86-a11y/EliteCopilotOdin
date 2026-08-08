"""Mensaje preparado para el futuro sintetizador de voz de ODIN."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VoiceMessageReady:
    officer: str
    message: str
    reason: str
    body_name: str = ""
