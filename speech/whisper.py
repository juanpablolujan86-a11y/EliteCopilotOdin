"""Transcripción local en español mediante whisper.cpp."""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path


class TranscriptionError(RuntimeError):
    pass


class WhisperTranscriber:
    def __init__(
        self,
        data_root: Path | None = None,
        *,
        model_preference: str = "small",
        threads: int = 4,
    ) -> None:
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        root = data_root or local / "ODIN" / "speech"
        self.executable = root / "whisper.cpp" / "Release" / "whisper-cli.exe"
        base = root / "models" / "ggml-base.bin"
        small = root / "models" / "ggml-small.bin"
        if model_preference == "base":
            self.model = base
        elif model_preference == "small":
            self.model = (
                small
                if small.exists() and small.stat().st_size > 450_000_000
                else base
            )
        else:
            raise ValueError("El modelo de Whisper debe ser 'base' o 'small'.")
        self.threads = max(1, min(int(threads), 4))

    def transcribe(self, audio: Path) -> str:
        if not self.executable.exists() or not self.model.exists():
            raise TranscriptionError("Falta instalar el motor local de reconocimiento de voz.")
        # Cada proceso recibe un archivo propio. Esto evita lecturas parciales si
        # dos solicitudes de voz llegan casi al mismo tiempo.
        output_base = audio.parent / f"{audio.stem}-{uuid.uuid4().hex}"
        command = [
            str(self.executable), "-m", str(self.model), "-f", str(audio),
            "-l", "es", "-nt", "-otxt", "-of", str(output_base),
            "-t", str(self.threads), "-ng", "-sns", "--prompt",
            "ODIN, MÍMIR, HEIMDALL, Elite Dangerous, Colonia, "
            "Stratum Tectonicas, exobiología, ruta de neutrones",
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120, check=False,
                creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise TranscriptionError(f"Falló el reconocimiento de voz: {error}") from error
        transcript = output_base.with_suffix(".txt")
        if result.returncode != 0 or not transcript.exists():
            detail = (result.stderr or result.stdout).strip()
            raise TranscriptionError(detail or "Whisper no pudo transcribir el audio.")
        try:
            raw_text = transcript.read_bytes()
            try:
                text = raw_text.decode("utf-8-sig").strip()
            except UnicodeDecodeError:
                # Algunas compilaciones de whisper.cpp heredan la página de
                # códigos de Windows para caracteres acentuados.
                text = raw_text.decode("cp1252", errors="replace").strip()
        finally:
            transcript.unlink(missing_ok=True)
        meaningful = "".join(character for character in text if character.isalnum())
        if len(meaningful) < 3:
            raise TranscriptionError("No se detectó una frase clara.")
        return text
