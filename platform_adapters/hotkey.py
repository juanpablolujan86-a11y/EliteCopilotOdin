"""Fachada para teclas globales sin acoplar el núcleo a Windows."""

from __future__ import annotations

import platform
from typing import Protocol, runtime_checkable


VK_F7 = 0x76
VK_F8 = 0x77


@runtime_checkable
class HotkeyAdapter(Protocol):
    def pressed(self) -> bool: ...


class HotkeyUnavailable(RuntimeError):
    pass


def create_hotkey(virtual_key: int = VK_F8) -> HotkeyAdapter:
    system = platform.system()
    if system == "Windows":
        from speech.hotkey import WindowsHotkey

        return WindowsHotkey(virtual_key)
    raise HotkeyUnavailable(
        f"ODIN todavía no dispone de teclas globales para {system or 'este sistema'}."
    )
