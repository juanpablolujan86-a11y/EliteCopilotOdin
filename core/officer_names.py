"""Nombres públicos de los oficiales sin alterar sus identificadores internos."""

from __future__ import annotations


PUBLIC_OFFICER_NAMES = {
    # Compatibilidad: HEIMDALL continúa siendo el ID interno de navegación.
    "HEIMDALL": "NJÖRÐR",
    # La sección tecnológica Guardian adopta el nombre público HEIMDALL.
    "GUARDIAN": "HEIMDALL",
    "INGENIERÍA": "VÖLUNDR",
    "ENGINEERING": "VÖLUNDR",
}


def public_officer_name(internal_name: str) -> str:
    """Devuelve el nombre visible sin modificar persistencia ni eventos."""

    normalized = str(internal_name).strip().upper()
    return PUBLIC_OFFICER_NAMES.get(normalized, str(internal_name).strip())
