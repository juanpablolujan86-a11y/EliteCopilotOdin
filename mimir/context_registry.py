"""Memoria conversacional de predicciones científicas del sistema."""

from __future__ import annotations

from models.events.voice_message_ready import VoiceMessageReady
from models.officer_report import OfficerReport
from core.body_names import body_designation


class ScientificContextRegistry:
    PRIORITY_SPECIES = ("Stratum Tectonicas", "Recepta Umbrux")

    def __init__(self) -> None:
        self._systems: dict[str, dict[str, tuple[str, ...]]] = {}
        self._priority_announced: set[tuple[str, str, str]] = set()

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

        probable_by_name = {
            species.casefold(): species for species in report.probable_species
        }
        priority_candidates = [
            probable_by_name[name.casefold()]
            for name in self.PRIORITY_SPECIES
            if name.casefold() in probable_by_name
            and (
                system.casefold(), body.casefold(), name.casefold()
            ) not in self._priority_announced
        ]
        if not announce or not priority_candidates:
            return None
        for species in priority_candidates:
            self._priority_announced.add(
                (system.casefold(), body.casefold(), species.casefold())
            )
        species_text = " y ".join(priority_candidates)
        return VoiceMessageReady(
            officer="MÍMIR",
            message=(
                f"Comandante, el planeta {body_designation(system, body)} podría contener "
                f"{species_text}. Recomiendo revisarlo."
            ),
            reason=f"Posible {species_text}",
            body_name=body,
        )

    def system_predictions(self, system_name: str) -> dict[str, tuple[str, ...]]:
        return dict(self._systems.get(system_name, {}))
