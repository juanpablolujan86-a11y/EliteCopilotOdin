"""Reproducción de MP3 mediante la API multimedia nativa de Windows."""

from __future__ import annotations

import ctypes
import subprocess
import tempfile
import uuid
from pathlib import Path


class AudioPlaybackError(RuntimeError):
    pass


class WindowsMp3Player:
    def __init__(self, cache_directory: Path | None = None) -> None:
        self.cache_directory = cache_directory or Path(tempfile.gettempdir()) / "ODIN"
        self._winmm = ctypes.WinDLL("winmm.dll")
        self._send = self._winmm.mciSendStringW
        self._send.argtypes = (
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint,
            ctypes.c_void_p,
        )
        self._send.restype = ctypes.c_uint

    def _command(self, command: str) -> None:
        error = self._send(command, None, 0, None)
        if error:
            raise AudioPlaybackError(f"Windows no pudo reproducir el audio ({error}).")

    def play(self, audio: bytes) -> None:
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        path = self.cache_directory / f"voice-{uuid.uuid4().hex}.mp3"
        alias = f"odinvoice{uuid.uuid4().hex}"
        path.write_bytes(audio)
        try:
            self._command(f'open "{path}" type mpegvideo alias {alias}')
            try:
                self._command(f"play {alias} wait")
            finally:
                self._send(f"close {alias}", None, 0, None)
        finally:
            path.unlink(missing_ok=True)


class WindowsSpeechPlayer:
    """Respaldo sin créditos mediante System.Speech de Windows."""

    SCRIPT = r"""
Add-Type -AssemblyName System.Speech
$text = [Console]::In.ReadToEnd()
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.Speak($text)
$speaker.Dispose()
"""

    def speak(self, text: str) -> None:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", self.SCRIPT],
            input=text,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if result.returncode:
            raise AudioPlaybackError("Windows no pudo usar la voz local de respaldo.")
