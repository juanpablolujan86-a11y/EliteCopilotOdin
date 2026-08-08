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


@dataclass(frozen=True, slots=True)
class ElevenLabsVoice:
    voice_id: str
    name: str
    category: str


class ElevenLabsError(RuntimeError):
    """Error seguro para mostrar sin exponer la credencial."""


class ElevenLabsClient:
    BASE_URL = "https://api.elevenlabs.io/v1"

    def _get(self, path: str, api_key: str) -> dict:
        if not api_key.strip():
            raise ElevenLabsError("La clave no puede estar vacía.")
        try:
            response = requests.get(
                f"{self.BASE_URL}{path}",
                headers={"xi-api-key": api_key, "Accept": "application/json"},
                timeout=15,
            )
        except requests.RequestException as error:
            raise ElevenLabsError(
                "No se pudo conectar con ElevenLabs."
            ) from error
        if response.status_code in {401, 403}:
            raise ElevenLabsError("ElevenLabs rechazó la clave API.")
        try:
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            raise ElevenLabsError(
                "ElevenLabs devolvió una respuesta inválida."
            ) from error

    def validate(self, api_key: str) -> ElevenLabsSubscription:
        payload = self._get("/user/subscription", api_key)
        return ElevenLabsSubscription(
            tier=str(payload.get("tier", "desconocido")),
            status=str(payload.get("status", "desconocido")),
            used=int(payload.get("character_count", 0) or 0),
            limit=int(payload.get("character_limit", 0) or 0),
        )

    def list_voices(self, api_key: str) -> tuple[ElevenLabsVoice, ...]:
        payload = self._get("/voices", api_key)
        voices = (
            ElevenLabsVoice(
                voice_id=str(item.get("voice_id", "")),
                name=str(item.get("name", "Sin nombre")),
                category=str(item.get("category", "")),
            )
            for item in payload.get("voices", [])
            if item.get("voice_id")
        )
        return tuple(sorted(voices, key=lambda voice: voice.name.casefold()))
