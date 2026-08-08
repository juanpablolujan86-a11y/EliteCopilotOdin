"""Referencias breves para cuerpos del sistema actual."""

from __future__ import annotations


def body_designation(system_name: str, body_name: str) -> str:
    """Quita el nombre del sistema cuando el cuerpo ya pertenece a él."""

    system = system_name.strip()
    body = body_name.strip()
    if system and body.casefold().startswith(f"{system.casefold()} "):
        return body[len(system):].strip()
    return body


def planet_reference(system_name: str, body_name: str) -> str:
    designation = body_designation(system_name, body_name)
    return f"planeta {designation}" if designation else "planeta desconocido"
