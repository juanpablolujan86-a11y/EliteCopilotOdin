"""Selección del emisor de controles físicos de cabina."""

from __future__ import annotations

import platform
from typing import Protocol, runtime_checkable

from heimdall.bindings import BindingInput


@runtime_checkable
class CockpitControlSender(Protocol):
    def send(self, binding: BindingInput) -> bool: ...


class CockpitControlUnavailable(RuntimeError):
    pass


def create_cockpit_sender() -> CockpitControlSender:
    system = platform.system()
    if system == "Windows":
        from heimdall.docking_assist import WindowsEliteKeySender

        return WindowsEliteKeySender()
    raise CockpitControlUnavailable(
        f"ODIN todavía no dispone de controles de cabina para {system or 'este sistema'}."
    )
