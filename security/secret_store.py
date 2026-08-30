"""Abstracción del almacén seguro de secretos de ODIN."""

from __future__ import annotations

import platform
from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretStore(Protocol):
    """Contrato mínimo que debe implementar el llavero seguro de cada SO."""

    def set(self, secret: str) -> None: ...
    def get(self) -> str | None: ...
    def delete(self) -> bool: ...
    def exists(self) -> bool: ...


class SecretStoreUnavailable(RuntimeError):
    """No hay un almacén seguro implementado para el sistema operativo actual."""


def create_secret_store(target: str) -> SecretStore:
    """Selecciona un almacén seguro; nunca degrada a texto plano."""

    system = platform.system()
    if system == "Windows":
        from voice.credentials import WindowsCredentialStore

        return WindowsCredentialStore(target)
    raise SecretStoreUnavailable(
        f"ODIN todavía no dispone de un almacén seguro para {system or 'este sistema'}."
    )
