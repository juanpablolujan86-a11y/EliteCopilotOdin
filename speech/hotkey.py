"""Detección no bloqueante de una tecla global en Windows."""

from __future__ import annotations

import ctypes


class WindowsHotkey:
    VK_F8 = 0x77

    def __init__(self, virtual_key: int = VK_F8) -> None:
        self.virtual_key = virtual_key
        self._was_down = False

    def pressed(self) -> bool:
        down = bool(ctypes.windll.user32.GetAsyncKeyState(self.virtual_key) & 0x8000)
        rising_edge = down and not self._was_down
        self._was_down = down
        return rising_edge
