"""Arranque local y silencioso del servidor Ollama usado por ODIN."""

from __future__ import annotations

import os
import subprocess
import time
import urllib.request
from pathlib import Path

from platform_adapters.process import hidden_process_flags


def ollama_executable() -> Path | None:
    candidates = (
        Path(os.environ.get("OLLAMA_EXE", "")),
        Path("D:/Ollama/ollama.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Ollama/ollama.exe",
    )
    return next((path for path in candidates if str(path) and path.is_file()), None)


def ollama_server_available(timeout: float = 0.6) -> bool:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/tags", timeout=timeout
        ) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def ensure_ollama_server(wait_seconds: float = 15.0) -> bool:
    """Inicia `ollama serve` sin consola cuando la instalacion ya existe."""

    if ollama_server_available():
        return True
    executable = ollama_executable()
    if executable is None:
        return False
    try:
        subprocess.Popen(
            [str(executable), "serve"], cwd=str(executable.parent),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=hidden_process_flags(detached=True),
        )
    except OSError:
        return False
    deadline = time.monotonic() + max(0.0, wait_seconds)
    while time.monotonic() < deadline:
        if ollama_server_available():
            return True
        time.sleep(0.2)
    return ollama_server_available()
