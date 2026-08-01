# ============================================================
# ODIN
#
# Versión : 0.2.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
mimir.species_predictor

Predicción de especies biológicas utilizando
la Enciclopedia Galáctica y el RuleEngine.
"""

import json
from pathlib import Path
from typing import Any

from mimir.rule_engine import RuleEngine
from models.prediction import Prediction
from models.species import Species
from knowledge.external.explodata.genus_data import data as genus_data


class SpeciesPredictor:
    """
    Busca especies compatibles con las condiciones
    observadas en un planeta.
    """

    def __init__(
        self,
        species_file: Path,
        rules_file: Path,
    ) -> None:
        self.rule_engine = RuleEngine()

        self._species = self._load_species(
            species_file
        )

        self._rules = self._load_rules(
            rules_file
        )

    def _load_json(
        self,
        path: Path,
    ) -> dict[str, Any]:
        """
        Carga un documento JSON.
        """

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    def _load_species(
        self,
        path: Path,
    ) -> dict[str, Species]:
        """
        Carga las especies indexadas por ID.
        """

        document = self._load_json(path)

        species_by_id: dict[str, Species] = {}

        for item in document.get(
            "species",
            [],
        ):
            species = Species(
                id=item["id"],
                name=item["name"],
                genus=item["genus"],
                genus_codex_id=item["genus_codex_id"],
                codex_id=item.get("codex_id", ""),
                value=item.get(
                    "value",
                    0,
                ),
            )

            species_by_id[
                species.id
            ] = species

        return species_by_id

    def _load_rules(
        self,
        path: Path,
    ) -> list[dict[str, Any]]:
        """
        Carga las reglas de predicción.
        """

        document = self._load_json(path)

        return document.get(
            "rules",
            [],
        )

    def predict(
        self,
        planet: dict[str, Any],
        confirmed_genus_ids: tuple[str, ...] = (),
    ) -> list[Prediction]:
        """
        Devuelve una sola predicción por especie,
        utilizando su mejor regla compatible.
        """

        best_results: dict[
            str,
            Prediction,
        ] = {}

        for rule_entry in self._rules:
            score, matches = (
                self.rule_engine.evaluate(
                    planet,
                    rule_entry["conditions"],
                )
            )

            if score == 0:
                continue

            species_id = rule_entry[
                "species"
            ]

            species = self._species.get(
                species_id
            )

            if species is None:
                continue

            if (
                confirmed_genus_ids
                and species.genus_codex_id not in confirmed_genus_ids
            ):
                continue

            prediction = Prediction(
                species=species,
                score=score,
                rule_id=rule_entry[
                    "rule_id"
                ],
                matches=matches,
                variants=self._predict_variants(species, planet),
            )

            current = best_results.get(
                species_id
            )

            if (
                current is None
                or prediction.score
                > current.score
            ):
                best_results[
                    species_id
                ] = prediction

        results = list(
            best_results.values()
        )

        results.sort(
            key=lambda item: (
                item.score,
                item.species.value,
            ),
            reverse=True,
        )

        return results

    def _predict_variants(
        self,
        species: Species,
        planet: dict[str, Any],
    ) -> tuple[str, ...]:
        """Predice colores usando estrella o materiales, como BioScan."""

        genus = genus_data.get(species.genus_codex_id, {})
        colors = genus.get("colors", {})
        species_colors = colors.get("species", {}).get(
            species.codex_id,
            {},
        )
        color_rules = species_colors or colors
        variants: set[str] = set()

        star_colors = color_rules.get("star", {})
        for expected_star, color in star_colors.items():
            if self.rule_engine._stars_match(
                planet.get("stars", []),
                [expected_star],
            ):
                variants.add(str(color))

        element_colors = color_rules.get("element", {})
        materials = planet.get("materials", {})
        for element, color in element_colors.items():
            if float(materials.get(element.lower(), 0)) > 0:
                variants.add(str(color))

        return tuple(sorted(variants))
