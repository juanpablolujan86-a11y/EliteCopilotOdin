"""Protección para impedir que dos copias de ODIN se ejecuten a la vez."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    """Mutex de Windows compartido por todas las distribuciones de ODIN."""

    def __init__(self, name: str = "Local\\EliteCopilotODIN") -> None:
        self.name = name
        self._handle: int | None = None

    def acquire(self) -> bool:
        if self._handle is not None:
            return True

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        kernel32.CreateMutexW.restype = wintypes.HANDLE

        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())

        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False

        self._handle = handle
        return True

    def close(self) -> None:
        if self._handle is None:
            return

        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(self._handle)
        self._handle = None

    def __enter__(self) -> "SingleInstance":
        if not self.acquire():
            raise RuntimeError("ODIN ya está ejecutándose")
        return self

    def __exit__(self, *_args) -> None:
        self.close()
