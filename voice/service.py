"""Selección de la voz de cada oficial y síntesis protegida."""

from __future__ import annotations

from core.config import Config
from voice.credentials import WindowsCredentialStore
from voice.elevenlabs import ElevenLabsClient, ElevenLabsError
from voice.playback import AudioPlaybackError, WindowsMp3Player, WindowsSpeechPlayer
from voice.settings import VoiceSettingsRepository


class VoiceServiceError(RuntimeError):
    pass


class OfficerVoiceService:
    def __init__(
        self,
        config: Config | None = None,
        credentials: WindowsCredentialStore | None = None,
        client: ElevenLabsClient | None = None,
        player: WindowsMp3Player | None = None,
        windows_player: WindowsSpeechPlayer | None = None,
    ) -> None:
        self.config = config or Config()
        self.credentials = credentials or WindowsCredentialStore()
        self.client = client or ElevenLabsClient()
        self.player = player or WindowsMp3Player(self.config.data_root / "voice" / "cache")
        self.windows_player = windows_player or WindowsSpeechPlayer()
        self.repository = VoiceSettingsRepository(self.config.data_root)

    def speak(self, officer: str, text: str) -> None:
        settings = self.repository.load()
        assignment = settings.officers.get(officer.upper())
        if not settings.enabled or assignment is None:
            raise VoiceServiceError(f"No hay una voz configurada para {officer}.")
        if assignment.provider == "windows":
            try:
                self.windows_player.speak(text)
                return
            except AudioPlaybackError as error:
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
                    self.windows_player.speak(text)
                    return
                except AudioPlaybackError:
                    pass
            raise VoiceServiceError(str(error)) from error
        finally:
            secret = ""
