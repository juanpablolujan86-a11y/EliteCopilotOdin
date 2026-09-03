"""Selección de la voz de cada oficial y síntesis protegida."""

from __future__ import annotations

import hashlib
from pathlib import Path

from core.config import Config
from platform_adapters.audio import (
    AudioPlayer,
    SpeechPlayer,
    create_audio_player,
    create_speech_player,
)
from security.secret_store import SecretStore, create_secret_store
from voice.credentials import ELEVENLABS_TARGET
from voice.edge import EdgeTtsClient, EdgeTtsError
from voice.elevenlabs import ElevenLabsClient, ElevenLabsError
from voice.kokoro import KokoroTtsClient, KokoroTtsError
from voice.playback import AudioPlaybackError
from voice.settings import VoiceSettingsRepository


class VoiceServiceError(RuntimeError):
    pass


WINDOWS_FALLBACKS = {
    "ODIN": ("Microsoft Raul - Spanish (Mexico)", 0),
    "MÍMIR": ("Microsoft Sabina - Spanish (Mexico)", 0),
    "HEIMDALL": ("Microsoft Raul - Spanish (Mexico)", -2),
    "FREYJA": ("Microsoft Sabina - Spanish (Mexico)", 1),
}


class OfficerVoiceService:
    def __init__(
        self,
        config: Config | None = None,
        credentials: SecretStore | None = None,
        client: ElevenLabsClient | None = None,
        player: AudioPlayer | None = None,
        windows_player: SpeechPlayer | None = None,
        edge_client: EdgeTtsClient | None = None,
        kokoro_client: KokoroTtsClient | None = None,
    ) -> None:
        self.config = config or Config()
        self.credentials = credentials or create_secret_store(ELEVENLABS_TARGET)
        self.client = client or ElevenLabsClient()
        self.player = player or create_audio_player(self.config.data_root / "voice" / "cache")
        self.windows_player = windows_player or create_speech_player()
        self.edge_client = edge_client or EdgeTtsClient()
        kokoro_root = getattr(
            self.config,
            "kokoro_model_root",
            self.config.data_root / "voice" / "models" / "kokoro-int8-multi-lang-v1_0",
        )
        self.kokoro_client = kokoro_client or KokoroTtsClient(kokoro_root)
        self.repository = VoiceSettingsRepository(self.config.data_root)

    def _edge_cache_path(self, officer: str, text: str, assignment) -> Path:
        cache_key = "|".join(
            (
                officer.upper(), assignment.voice, str(assignment.rate),
                str(assignment.volume), text,
            )
        )
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return self.config.data_root / "voice" / "cache" / f"edge-{digest}.mp3"

    def _kokoro_cache_path(self, officer: str, text: str, assignment) -> Path:
        cache_key = "|".join((officer.upper(), assignment.voice, str(assignment.rate), text))
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return self.config.data_root / "voice" / "cache" / f"kokoro-{digest}.wav"

    def prepare(self, officer: str, text: str) -> None:
        """Genera anticipadamente una frase Edge repetitiva sin reproducirla."""

        settings = self.repository.load()
        assignment = settings.officers.get(officer.upper())
        if not settings.enabled or assignment is None or assignment.provider != "edge":
            return
        cache_path = self._edge_cache_path(officer, text, assignment)
        if cache_path.exists():
            return
        try:
            audio = self.edge_client.synthesize(
                text, assignment.voice, rate=assignment.rate, volume=assignment.volume
            )
        except (EdgeTtsError, OSError) as error:
            raise VoiceServiceError(str(error)) from error
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(audio)

    def speak(self, officer: str, text: str) -> None:
        settings = self.repository.load()
        assignment = settings.officers.get(officer.upper())
        if not settings.enabled or assignment is None:
            raise VoiceServiceError(f"No hay una voz configurada para {officer}.")
        if assignment.provider == "windows":
            try:
                self.windows_player.speak(
                    text, assignment.voice, assignment.rate, assignment.volume
                )
                return
            except AudioPlaybackError as error:
                raise VoiceServiceError(str(error)) from error
        if assignment.provider == "edge":
            try:
                cache_path = self._edge_cache_path(officer, text, assignment)
                if cache_path.exists():
                    audio = cache_path.read_bytes()
                else:
                    audio = self.edge_client.synthesize(
                        text, assignment.voice,
                        rate=assignment.rate, volume=assignment.volume,
                    )
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(audio)
                self.player.play(audio)
                return
            except (EdgeTtsError, AudioPlaybackError, OSError) as error:
                if settings.fallback_to_windows:
                    fallback_voice, fallback_rate = WINDOWS_FALLBACKS.get(
                        officer.upper(), WINDOWS_FALLBACKS["ODIN"]
                    )
                    try:
                        self.windows_player.speak(
                            text, fallback_voice, fallback_rate, assignment.volume
                        )
                        return
                    except AudioPlaybackError:
                        pass
                raise VoiceServiceError(str(error)) from error
        if assignment.provider == "kokoro":
            try:
                cache_path = self._kokoro_cache_path(officer, text, assignment)
                if cache_path.exists():
                    audio = cache_path.read_bytes()
                else:
                    speed = max(0.5, min(2.0, 1.0 + assignment.rate * 0.05))
                    audio = self.kokoro_client.synthesize(
                        text, assignment.voice, speed=speed
                    )
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(audio)
                self.player.play(audio)
                return
            except (KokoroTtsError, AudioPlaybackError, OSError) as error:
                if settings.fallback_to_windows:
                    fallback_voice, fallback_rate = WINDOWS_FALLBACKS.get(
                        officer.upper(), WINDOWS_FALLBACKS["ODIN"]
                    )
                    try:
                        self.windows_player.speak(
                            text, fallback_voice, fallback_rate, assignment.volume
                        )
                        return
                    except AudioPlaybackError:
                        pass
                raise VoiceServiceError(str(error)) from error
        secret = self.credentials.get()
        if not secret:
            raise VoiceServiceError("No hay una clave de ElevenLabs protegida en Windows.")
        try:
            audio = self.client.synthesize(secret, assignment.voice, text)
            self.player.play(audio)
        except (ElevenLabsError, AudioPlaybackError, OSError) as error:
            if settings.fallback_to_windows:
                try:
                    fallback_voice, fallback_rate = WINDOWS_FALLBACKS.get(
                        officer.upper(), WINDOWS_FALLBACKS["ODIN"]
                    )
                    self.windows_player.speak(
                        text, fallback_voice, fallback_rate, assignment.volume
                    )
                    return
                except AudioPlaybackError:
                    pass
            raise VoiceServiceError(str(error)) from error
        finally:
            secret = ""
