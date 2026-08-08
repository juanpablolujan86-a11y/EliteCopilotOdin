"""Síntesis neuronal gratuita mediante el servicio de lectura de Edge."""

from __future__ import annotations

import edge_tts


class EdgeTtsError(RuntimeError):
    pass


EDGE_LATIN_VOICES = {
    "ODIN": "es-AR-TomasNeural",
    "MÍMIR": "es-MX-DaliaNeural",
    "HEIMDALL": "es-MX-JorgeNeural",
}


class EdgeTtsClient:
    def synthesize(self, text: str, voice: str, *, rate: int = 0, volume: int = 100) -> bytes:
        rate_percent = max(-50, min(50, rate * 10))
        volume_percent = max(-100, min(0, volume - 100))
        try:
            communication = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=f"{rate_percent:+d}%",
                volume=f"{volume_percent:+d}%",
            )
            audio = b"".join(
                item["data"]
                for item in communication.stream_sync()
                if item.get("type") == "audio" and item.get("data")
            )
        except Exception as error:
            raise EdgeTtsError("Edge TTS no está disponible; se usará Windows.") from error
        if not audio:
            raise EdgeTtsError("Edge TTS devolvió un audio vacío.")
        return audio
