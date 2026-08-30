"""Selección de la protección de instancia única según la plataforma."""

from __future__ import annotations

import platform
from typing import Protocol, runtime_checkable


@runtime_checkable
class SingleInstanceAdapter(Protocol):
    def acquire(self) -> bool: ...
    def close(self) -> None: ...


class SingleInstanceUnavailable(RuntimeError):
    pass


def create_single_instance(name: str = "Local\\EliteCopilotODIN") -> SingleInstanceAdapter:
    system = platform.system()
    if system == "Windows":
        from core.single_instance import SingleInstance

        return SingleInstance(name)
    raise SingleInstanceUnavailable(
        f"ODIN todavía no dispone de bloqueo de instancia para {system or 'este sistema'}."
    )
