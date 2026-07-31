"""
knowledge.importer.normalizer

Normalización del conocimiento adquirido por HUGINN.

Todas las fuentes externas son convertidas al
modelo oficial de la Enciclopedia Galáctica.
"""

from typing import Any


class KnowledgeNormalizer:

    def normalize_species(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:

        return {

            "id": data.get("id"),

            "genus": data.get("genus"),

            "species": data.get("species"),

            "variant": data.get("variant"),

            "rarity": data.get("rarity"),

            "estimated_value": data.get(
                "estimated_value",
                0,
            ),

            "sampling_distance": data.get(
                "sampling_distance",
                0,
            ),

            "planet_classes": data.get(
                "planet_classes",
                [],
            ),

            "atmospheres": data.get(
                "atmospheres",
                [],
            ),

            "gravity": data.get(
                "gravity",
                {},
            ),

            "temperature": data.get(
                "temperature",
                {},
            ),

            "volcanism": data.get(
                "volcanism",
                [],
            ),

            "star_types": data.get(
                "star_types",
                [],
            ),

            "sources": data.get(
                "sources",
                [],
            ),

            "confidence": data.get(
                "confidence",
                1.0,
            )
        }