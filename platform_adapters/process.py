"""Opciones de procesos secundarios traducidas por plataforma."""

from __future__ import annotations

import platform
import subprocess


def hidden_process_flags(*, detached: bool = False, below_normal: bool = False) -> int:
    """Devuelve únicamente flags válidos en la plataforma actual."""

    if platform.system() != "Windows":
        return 0
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if detached:
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    if below_normal:
        flags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    return flags
