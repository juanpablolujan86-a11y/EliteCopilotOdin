"""Validación de la biblioteca biológica generada por HUGINN."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BiologyValidationReport:
    species_count: int
    rules_count: int
    genus_count: int
    species_without_rules: tuple[str, ...]
    duplicate_species_ids: tuple[str, ...]
    duplicate_rule_ids: tuple[str, ...]
    rules_without_species: tuple[str, ...]
    empty_rule_ids: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not (
            self.duplicate_species_ids
            or self.duplicate_rule_ids
            or self.rules_without_species
            or self.empty_rule_ids
        )


class BiologyKnowledgeValidator:
    """Comprueba referencias e identificadores de especies y reglas."""

    def validate(
        self,
        species: list[dict],
        rules: list[dict],
    ) -> BiologyValidationReport:
        species_ids = [item["id"] for item in species]
        rule_ids = [item["rule_id"] for item in rules]
        referenced_species = {item["species"] for item in rules}
        known_species = set(species_ids)

        return BiologyValidationReport(
            species_count=len(species),
            rules_count=len(rules),
            genus_count=len({item["genus"] for item in species}),
            species_without_rules=tuple(
                sorted(known_species - referenced_species)
            ),
            duplicate_species_ids=self._duplicates(species_ids),
            duplicate_rule_ids=self._duplicates(rule_ids),
            rules_without_species=tuple(
                sorted(referenced_species - known_species)
            ),
            empty_rule_ids=tuple(
                sorted(
                    item["rule_id"]
                    for item in rules
                    if not item.get("conditions")
                )
            ),
        )

    @staticmethod
    def _duplicates(values: list[str]) -> tuple[str, ...]:
        counts = Counter(values)
        return tuple(
            sorted(value for value, count in counts.items() if count > 1)
        )
