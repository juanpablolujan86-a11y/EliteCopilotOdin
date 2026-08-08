"""Selección de la voz de cada oficial y síntesis protegida."""

from __future__ import annotations

from core.config import Config
from voice.credentials import WindowsCredentialStore
from voice.edge import EdgeTtsClient, EdgeTtsError
from voice.elevenlabs import ElevenLabsClient, ElevenLabsError
from voice.playback import AudioPlaybackError, WindowsMp3Player, WindowsSpeechPlayer
from voice.settings import VoiceSettingsRepository


class VoiceServiceError(RuntimeError):
    pass


WINDOWS_FALLBACKS = {
    "ODIN": ("Microsoft Raul - Spanish (Mexico)", 0),
    "MÍMIR": ("Microsoft Sabina - Spanish (Mexico)", 0),
    "HEIMDALL": ("Microsoft Raul - Spanish (Mexico)", -2),
}


class OfficerVoiceService:
    def __init__(
        self,
        config: Config | None = None,
        credentials: WindowsCredentialStore | None = None,
        client: ElevenLabsClient | None = None,
        player: WindowsMp3Player | None = None,
        windows_player: WindowsSpeechPlayer | None = None,
        edge_client: EdgeTtsClient | None = None,
    ) -> None:
        self.config = config or Config()
        self.credentials = credentials or WindowsCredentialStore()
        self.client = client or ElevenLabsClient()
        self.player = player or WindowsMp3Player(self.config.data_root / "voice" / "cache")
        self.windows_player = windows_player or WindowsSpeechPlayer()
        self.edge_client = edge_client or EdgeTtsClient()
        self.repository = VoiceSettingsRepository(self.config.data_root)

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
                audio = self.edge_client.synthesize(
                    text, assignment.voice, rate=assignment.rate, volume=assignment.volume
                )
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
