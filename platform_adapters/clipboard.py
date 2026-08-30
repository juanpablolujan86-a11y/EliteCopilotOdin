"""Fachada de portapapeles seleccionada según la plataforma."""

from __future__ import annotations

import platform
from typing import Protocol, runtime_checkable


@runtime_checkable
class ClipboardAdapter(Protocol):
    def write_text(self, text: str) -> None: ...


class ClipboardUnavailable(RuntimeError):
    pass


class WindowsClipboardAdapter:
    def write_text(self, text: str) -> None:
        from heimdall.clipboard import write_text

        write_text(text)


def create_clipboard() -> ClipboardAdapter:
    system = platform.system()
    if system == "Windows":
        return WindowsClipboardAdapter()
    raise ClipboardUnavailable(
        f"ODIN todavía no dispone de portapapeles para {system or 'este sistema'}."
    )


def copy_text(text: str) -> None:
    """Copia texto usando el adaptador seguro de la plataforma actual."""

    create_clipboard().write_text(text)
