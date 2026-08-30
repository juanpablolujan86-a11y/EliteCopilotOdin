"""Preferencias no secretas de las voces de cada oficial."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(slots=True)
class OfficerVoice:
    provider: str = "windows"
    voice: str = ""
    rate: int = 0
    volume: int = 100


@dataclass(slots=True)
class VoiceSettings:
    enabled: bool = True
    fallback_to_windows: bool = True
    officers: dict[str, OfficerVoice] = field(default_factory=lambda: {
        "ODIN": OfficerVoice(provider="edge", voice="es-US-AlonsoNeural"),
        "MÍMIR": OfficerVoice(provider="edge", voice="es-MX-DaliaNeural"),
        "HEIMDALL": OfficerVoice(provider="edge", voice="es-MX-JorgeNeural"),
        "FREYJA": OfficerVoice(provider="edge", voice="es-AR-ElenaNeural", rate=1),
        "BROKK": OfficerVoice(provider="edge", voice="es-MX-JorgeNeural"),
    })


class VoiceSettingsRepository:
    def __init__(self, data_root: Path) -> None:
        self.path = data_root / "voice" / "settings.json"

    def load(self) -> VoiceSettings:
        if not self.path.exists():
            return VoiceSettings()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        defaults = VoiceSettings()
        officers = dict(defaults.officers)
        for name, item in payload.get("officers", {}).items():
            officers[name] = OfficerVoice(
                provider=str(item.get("provider", "windows")),
                voice=str(item.get("voice", "")),
                rate=int(item.get("rate", 0)),
                volume=int(item.get("volume", 100)),
            )
        return VoiceSettings(
            enabled=bool(payload.get("enabled", True)),
            fallback_to_windows=bool(payload.get("fallback_to_windows", True)),
            officers=officers,
        )

    def save(self, settings: VoiceSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


LANGUAGE_VOICE_PRESETS = {
    "es-419": {
        "ODIN": "es-US-AlonsoNeural", "MÍMIR": "es-MX-DaliaNeural",
        "HEIMDALL": "es-MX-JorgeNeural", "FREYJA": "es-AR-ElenaNeural",
        "BROKK": "es-MX-JorgeNeural",
    },
    "es-ES": {
        "ODIN": "es-ES-AlvaroNeural", "MÍMIR": "es-ES-ElviraNeural",
        "HEIMDALL": "es-ES-AlvaroNeural", "FREYJA": "es-ES-ElviraNeural",
        "BROKK": "es-ES-AlvaroNeural",
    },
    "en-US": {
        "ODIN": "en-US-GuyNeural", "MÍMIR": "en-US-JennyNeural",
        "HEIMDALL": "en-US-DavisNeural", "FREYJA": "en-US-AriaNeural",
        "BROKK": "en-US-TonyNeural",
    },
    "en-GB": {
        "ODIN": "en-GB-RyanNeural", "MÍMIR": "en-GB-SoniaNeural",
        "HEIMDALL": "en-GB-ThomasNeural", "FREYJA": "en-GB-LibbyNeural",
        "BROKK": "en-GB-RyanNeural",
    },
    "pt-BR": {
        "ODIN": "pt-BR-AntonioNeural", "MÍMIR": "pt-BR-FranciscaNeural",
        "HEIMDALL": "pt-BR-AntonioNeural", "FREYJA": "pt-BR-FranciscaNeural",
        "BROKK": "pt-BR-AntonioNeural",
    },
}


def apply_language_voice_preset(settings: VoiceSettings, language: str) -> None:
    """Asigna voces Edge del idioma conservando volumen y velocidad."""

    from core.localization import normalize_language

    preset = LANGUAGE_VOICE_PRESETS[normalize_language(language)]
    for officer, voice in preset.items():
        assignment = settings.officers.setdefault(officer, OfficerVoice())
        assignment.provider = "edge"
        assignment.voice = voice
