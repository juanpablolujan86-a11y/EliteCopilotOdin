"""Escritura mínima y explícita en el portapapeles de Windows."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes


class ClipboardError(RuntimeError):
    pass


def write_text(text: str) -> None:
    """Copia texto Unicode sin simular teclas ni interactuar con Elite."""

    if not text:
        raise ValueError("No se puede copiar un sistema vacío.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]

    for attempt in range(5):
        if user32.OpenClipboard(None):
            break
        if attempt == 4:
            raise ClipboardError("Windows no permitió abrir el portapapeles.")
        time.sleep(0.05 * (attempt + 1))

    handle = None
    transferred = False
    try:
        if not user32.EmptyClipboard():
            raise ClipboardError("No se pudo vaciar el portapapeles.")
        encoded = (text + "\0").encode("utf-16-le")
        handle = kernel32.GlobalAlloc(0x0002, len(encoded))  # GMEM_MOVEABLE
        if not handle:
            raise ClipboardError("No se pudo reservar memoria para el texto.")
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise ClipboardError("No se pudo bloquear la memoria del portapapeles.")
        try:
            ctypes.memmove(pointer, encoded, len(encoded))
        finally:
            kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(13, handle):  # CF_UNICODETEXT
            raise ClipboardError("Windows rechazó el texto del portapapeles.")
        transferred = True
    finally:
        if handle and not transferred:
            kernel32.GlobalFree(handle)
        user32.CloseClipboard()
