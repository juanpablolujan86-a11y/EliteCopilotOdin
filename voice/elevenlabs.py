"""Validación mínima y segura de credenciales ElevenLabs."""

from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass(frozen=True, slots=True)
class ElevenLabsSubscription:
    tier: str
    status: str
    used: int
    limit: int


class ElevenLabsError(RuntimeError):
    """Error seguro para mostrar sin exponer la credencial."""


class ElevenLabsClient:
    BASE_URL = "https://api.elevenlabs.io/v1"

    def validate(self, api_key: str) -> ElevenLabsSubscription:
        if not api_key.strip():
            raise ElevenLabsError("La clave no puede estar vacía.")
        try:
            response = requests.get(
                f"{self.BASE_URL}/user/subscription",
                headers={"xi-api-key": api_key, "Accept": "application/json"},
                timeout=15,
            )
        except requests.RequestException as error:
            raise ElevenLabsError(
                "No se pudo conectar con ElevenLabs. La clave no fue guardada."
            ) from error
        if response.status_code in {401, 403}:
            raise ElevenLabsError("ElevenLabs rechazó la clave API.")
        try:
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise ElevenLabsError(
                "ElevenLabs devolvió una respuesta inválida. La clave no fue guardada."
            ) from error
        return ElevenLabsSubscription(
            tier=str(payload.get("tier", "desconocido")),
            status=str(payload.get("status", "desconocido")),
            used=int(payload.get("character_count", 0) or 0),
            limit=int(payload.get("character_limit", 0) or 0),
        )
