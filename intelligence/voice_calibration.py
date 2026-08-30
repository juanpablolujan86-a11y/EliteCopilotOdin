"""Calibración local y explícita de órdenes para cada comandante."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from array import array
from pathlib import Path
import wave

from intelligence.command_memory import VoiceCommandMemory


@dataclass(frozen=True, slots=True)
class CalibrationCommand:
    key: str
    phrase: str
    intent: str
    payload: dict[str, str]


CALIBRATION_COMMANDS = (
    CalibrationCommand("trade", "Quiero comerciar", "freyja_trade_menu", {}),
    CalibrationCommand("home", "Vamos a casa", "home_route", {}),
    CalibrationCommand("dock", "Solicita atraque", "docking_request", {}),
    CalibrationCommand(
        "night", "Luz nocturna", "cockpit_night_vision", {"state": "toggle"}
    ),
    CalibrationCommand(
        "scoop", "Colector de carga", "cockpit_cargo_scoop", {"state": "toggle"}
    ),
    CalibrationCommand(
        "gear", "Tren de aterrizaje", "cockpit_landing_gear", {"state": "toggle"}
    ),
    CalibrationCommand(
        "jump", "Hipersalto", "cockpit_hyperspace", {"state": "toggle"}
    ),
)


class VoiceCalibrationManager:
    def __init__(self, memory: VoiceCommandMemory) -> None:
        self.memory = memory
        self.database = memory.database

    def begin(self, commander: str) -> None:
        commander = self._commander(commander)
        now = self._now()
        self.database.execute(
            """
            INSERT INTO voice_calibration_profiles
                (commander_key, consented_at, updated_at, sample_count)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(commander_key) DO UPDATE SET updated_at=excluded.updated_at
            """,
            (commander, now, now),
        )

    def enroll(
        self, commander: str, transcript: str, command_key: str, *,
        duration: float | None = None, rms: float | None = None,
    ) -> None:
        commander = self._commander(commander)
        profile = self.status(commander)
        if not profile["consented"]:
            raise ValueError("La calibración requiere consentimiento explícito.")
        command = next(
            (item for item in CALIBRATION_COMMANDS if item.key == command_key), None
        )
        if command is None:
            raise ValueError("La orden de calibración no está permitida.")
        self.memory.remember(
            commander, transcript, command.intent, command.payload,
            source="calibration",
        )
        now = self._now()
        self.database.execute(
            """
            UPDATE voice_calibration_profiles
            SET updated_at=?, sample_count=(
                SELECT COUNT(*) FROM voice_command_memory
                WHERE commander_key=? AND source='calibration'
            ) WHERE commander_key=?
            """,
            (now, commander, commander),
        )
        if duration is not None and rms is not None and duration > 0 and rms > 0:
            self.database.execute(
                """
                UPDATE voice_calibration_profiles
                SET duration_total=duration_total+?, rms_total=rms_total+?,
                    acoustic_samples=acoustic_samples+1
                WHERE commander_key=?
                """,
                (min(float(duration), 12.0), min(float(rms), 32767.0), commander),
            )

    def status(self, commander: str) -> dict:
        commander = self._commander(commander)
        rows = self.database.query(
            """
            SELECT consented_at, updated_at, sample_count, duration_total,
                   rms_total, acoustic_samples
            FROM voice_calibration_profiles WHERE commander_key=?
            """,
            (commander,),
        )
        if not rows:
            return {
                "consented": False, "sample_count": 0, "updated_at": "",
                "acoustic_samples": 0, "average_duration": 0.0,
                "average_rms": 0.0, "silence_seconds": 1.0,
                "threshold_multiplier": 3.5,
            }
        row = rows[0]
        acoustic_samples = int(row["acoustic_samples"] or 0)
        average_duration = (
            float(row["duration_total"] or 0) / acoustic_samples
            if acoustic_samples else 0.0
        )
        average_rms = (
            float(row["rms_total"] or 0) / acoustic_samples
            if acoustic_samples else 0.0
        )
        return {
            "consented": True,
            "sample_count": self.memory.count(commander, source="calibration"),
            "updated_at": str(row["updated_at"]),
            "acoustic_samples": acoustic_samples,
            "average_duration": average_duration,
            "average_rms": average_rms,
            "silence_seconds": max(0.8, min(1.25, average_duration * 0.18))
            if acoustic_samples else 1.0,
            "threshold_multiplier": max(2.7, min(3.8, 3.5 - average_rms / 12000))
            if acoustic_samples else 3.5,
        }

    def delete(self, commander: str) -> int:
        commander = self._commander(commander)
        removed = self.memory.forget_commander(commander)
        self.database.execute(
            "DELETE FROM voice_calibration_profiles WHERE commander_key=?",
            (commander,),
        )
        return removed

    @staticmethod
    def _commander(commander: str) -> str:
        value = str(commander).strip()
        if not value:
            raise ValueError("No hay un comandante identificado.")
        return value

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


def analyze_calibration_wav(path: Path) -> tuple[float, float]:
    """Devuelve duración y RMS; no conserva ni transmite la grabación."""

    with wave.open(str(path), "rb") as audio:
        frames = audio.readframes(audio.getnframes())
        duration = audio.getnframes() / max(1, audio.getframerate())
        width = audio.getsampwidth()
    if width != 2:
        raise ValueError("La muestra acústica debe usar PCM de 16 bits.")
    samples = array("h")
    samples.frombytes(frames)
    rms = (
        (sum(sample * sample for sample in samples) / len(samples)) ** 0.5
        if samples else 0.0
    )
    return duration, rms
