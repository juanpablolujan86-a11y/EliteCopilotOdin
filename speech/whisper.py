"""Transcripción local en español mediante whisper.cpp."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class TranscriptionError(RuntimeError):
    pass


class WhisperTranscriber:
    def __init__(self, data_root: Path | None = None) -> None:
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        root = data_root or local / "ODIN" / "speech"
        self.executable = root / "whisper.cpp" / "Release" / "whisper-cli.exe"
        self.model = root / "models" / "ggml-base.bin"

    def transcribe(self, audio: Path) -> str:
        if not self.executable.exists() or not self.model.exists():
            raise TranscriptionError("Falta instalar el motor local de reconocimiento de voz.")
        output_base = audio.with_suffix("")
        command = [
            str(self.executable), "-m", str(self.model), "-f", str(audio),
            "-l", "es", "-nt", "-otxt", "-of", str(output_base),
            "-t", "4", "-ng", "-sns",
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise TranscriptionError(f"Falló el reconocimiento de voz: {error}") from error
        transcript = output_base.with_suffix(".txt")
        if result.returncode != 0 or not transcript.exists():
            detail = (result.stderr or result.stdout).strip()
            raise TranscriptionError(detail or "Whisper no pudo transcribir el audio.")
        text = transcript.read_text(encoding="utf-8-sig").strip()
        meaningful = "".join(character for character in text if character.isalnum())
        if len(meaningful) < 3:
            raise TranscriptionError("No se detectó una frase clara.")
        return text
