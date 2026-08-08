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
    verified_languages: tuple[tuple[str, str, str], ...] = ()

    @property
    def is_latin_spanish(self) -> bool:
        latin_accents = (
            "latin",
            "mexican",
            "colombian",
            "argentin",
            "chilean",
            "peruvian",
            "venezuel",
            "uruguay",
        )
        return any(
            language == "es" and any(marker in accent.casefold() for marker in latin_accents)
            for language, accent, _locale in self.verified_languages
        )


@dataclass(frozen=True, slots=True)
class ElevenLabsSharedVoice:
    voice_id: str
    owner_id: str
    name: str
    gender: str
    accent: str
    free_users_allowed: bool


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
                verified_languages=tuple(
                    (
                        str(language.get("language", "")),
                        str(language.get("accent", "")),
                        str(language.get("locale", "")),
                    )
                    for language in (item.get("verified_languages") or [])
                ),
            )
            for item in payload.get("voices", [])
            if item.get("voice_id")
        )
        return tuple(sorted(voices, key=lambda voice: voice.name.casefold()))

    def synthesize(
        self,
        api_key: str,
        voice_id: str,
        text: str,
        *,
        model_id: str = "eleven_multilingual_v2",
    ) -> bytes:
        if not api_key.strip() or not voice_id.strip() or not text.strip():
            raise ElevenLabsError("Faltan la clave, la voz o el texto para sintetizar.")
        try:
            response = requests.post(
                f"{self.BASE_URL}/text-to-speech/{voice_id}",
                params={"output_format": "mp3_44100_128"},
                headers={
                    "xi-api-key": api_key,
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                },
                json={"text": text, "model_id": model_id},
                timeout=60,
            )
        except requests.RequestException as error:
            raise ElevenLabsError("No se pudo conectar con la síntesis de ElevenLabs.") from error
        if response.status_code in {401, 403}:
            raise ElevenLabsError(
                "ElevenLabs rechazó la síntesis; revisá el permiso Text to Speech."
            )
        try:
            response.raise_for_status()
        except requests.RequestException as error:
            raise ElevenLabsError("ElevenLabs no pudo generar el audio.") from error
        if not response.content:
            raise ElevenLabsError("ElevenLabs devolvió un audio vacío.")
        return response.content

    def list_shared_latin_spanish_voices(
        self, api_key: str, accent: str = "latin"
    ) -> tuple[ElevenLabsSharedVoice, ...]:
        try:
            response = requests.get(
                f"{self.BASE_URL}/shared-voices",
                headers={"xi-api-key": api_key, "Accept": "application/json"},
                params={
                    "language": "es",
                    "accent": accent,
                    "page_size": 100,
                    "sort": "trending",
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise ElevenLabsError(
                "No se pudo consultar la biblioteca de voces latinas."
            ) from error
        return tuple(
            ElevenLabsSharedVoice(
                voice_id=str(item.get("voice_id", "")),
                owner_id=str(item.get("public_owner_id", "")),
                name=str(item.get("name", "Sin nombre")),
                gender=str(item.get("gender", "")),
                accent=str(item.get("accent", "")),
                free_users_allowed=bool(item.get("free_users_allowed", False)),
            )
            for item in payload.get("voices", [])
            if item.get("voice_id") and item.get("public_owner_id")
        )

    def add_shared_voice(
        self,
        api_key: str,
        owner_id: str,
        voice_id: str,
        name: str,
    ) -> str:
        try:
            response = requests.post(
                f"{self.BASE_URL}/voices/add/{owner_id}/{voice_id}",
                headers={
                    "xi-api-key": api_key,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={"new_name": name, "bookmarked": True},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise ElevenLabsError(f"No se pudo agregar la voz {name}.") from error
        added_id = str(payload.get("voice_id", ""))
        if not added_id:
            raise ElevenLabsError(f"ElevenLabs no devolvió el ID de {name}.")
        return added_id
