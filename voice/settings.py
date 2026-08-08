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
        "ODIN": OfficerVoice(provider="edge", voice="es-AR-TomasNeural"),
        "MÍMIR": OfficerVoice(provider="edge", voice="es-MX-DaliaNeural"),
        "HEIMDALL": OfficerVoice(provider="edge", voice="es-CO-GonzaloNeural"),
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
