"""Memoria conversacional de predicciones científicas del sistema."""

from __future__ import annotations

from models.events.voice_message_ready import VoiceMessageReady
from models.officer_report import OfficerReport
from core.body_names import body_designation
from core.localization import normalize_language, text


class ScientificContextRegistry:
    PRIORITY_SPECIES = ("Stratum Tectonicas", "Recepta Umbrux")

    def __init__(self, language: str = "es-419") -> None:
        self.language = normalize_language(language)
        self._systems: dict[str, dict[str, tuple[str, ...]]] = {}
        self._system_values: dict[str, dict[str, dict[str, int]]] = {}
        self._system_rewards: dict[str, dict[str, dict[str, tuple[int, int]]]] = {}
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
        system = system_name or text("mimir.unknown_system", self.language)
        body = report.body_name or text("mimir.unknown_body_name", self.language)
        self._systems.setdefault(system, {})[body] = tuple(report.probable_species)
        self._system_values.setdefault(system, {})[body] = {
            name: int(base_value)
            for name, base_value, _potential_value in report.probable_species_values
        }
        self._system_rewards.setdefault(system, {})[body] = {
            name: (int(base_value), int(potential_value))
            for name, base_value, potential_value in report.probable_species_values
        }

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
        species_text = text("common.and_join", self.language).join(priority_candidates)
        return VoiceMessageReady(
            officer="MÍMIR",
            message=text(
                "mimir.priority_alert", self.language,
                body=body_designation(system, body), species=species_text,
            ),
            reason=f"Posible {species_text}",
            body_name=body,
        )

    def system_predictions(self, system_name: str) -> dict[str, tuple[str, ...]]:
        return dict(self._systems.get(system_name, {}))

    def system_prediction_values(self, system_name: str) -> dict[str, dict[str, int]]:
        return {
            body: dict(values)
            for body, values in self._system_values.get(system_name, {}).items()
        }

    def system_prediction_rewards(
        self, system_name: str
    ) -> dict[str, dict[str, tuple[int, int]]]:
        return {
            body: dict(rewards)
            for body, rewards in self._system_rewards.get(system_name, {}).items()
        }
