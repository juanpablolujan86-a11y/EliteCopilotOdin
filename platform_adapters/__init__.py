"""Adaptadores que aíslan al núcleo de los servicios del sistema operativo."""

from platform_adapters.clipboard import ClipboardAdapter, copy_text, create_clipboard
from platform_adapters.hotkey import HotkeyAdapter, create_hotkey
from platform_adapters.single_instance import SingleInstanceAdapter, create_single_instance

__all__ = [
    "ClipboardAdapter", "copy_text", "create_clipboard",
    "HotkeyAdapter", "create_hotkey",
    "SingleInstanceAdapter", "create_single_instance",
]
