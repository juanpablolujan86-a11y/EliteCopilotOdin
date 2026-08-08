"""Memoria conversacional de predicciones científicas del sistema."""

from __future__ import annotations

from models.events.voice_message_ready import VoiceMessageReady
from models.officer_report import OfficerReport


class ScientificContextRegistry:
    def __init__(self) -> None:
        self._systems: dict[str, dict[str, tuple[str, ...]]] = {}
        self._tectonicas_announced: set[tuple[str, str]] = set()

    def record(
        self,
        system_name: str,
        report: OfficerReport,
        *,
        announce: bool = True,
    ) -> VoiceMessageReady | None:
        if not report.has_biological_signal or not report.probable_species:
            return None
        system = system_name or "Sistema desconocido"
        body = report.body_name or "Cuerpo desconocido"
        self._systems.setdefault(system, {})[body] = tuple(report.probable_species)

        tectonicas = next(
            (
                species for species in report.probable_species
                if species.casefold() == "stratum tectonicas"
            ),
            None,
        )
        key = (system.casefold(), body.casefold())
        if not announce or tectonicas is None or key in self._tectonicas_announced:
            return None
        self._tectonicas_announced.add(key)
        return VoiceMessageReady(
            officer="MÍMIR",
            message=(
                f"Comandante, el planeta {body} podría contener "
                "Stratum Tectonicas. Recomiendo revisarlo."
            ),
            reason="Posible Stratum Tectonicas",
            body_name=body,
        )

    def system_predictions(self, system_name: str) -> dict[str, tuple[str, ...]]:
        return dict(self._systems.get(system_name, {}))
