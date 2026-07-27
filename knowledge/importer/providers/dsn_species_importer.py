"""
knowledge.importer.providers.dsn_species_importer

Importador de especies provenientes de
Deep Space Network.

Convierte la estructura original al formato
interno utilizado por la Biblioteca de
Conocimiento de ODIN.
"""

from typing import Any

from knowledge.importer.converter import KnowledgeConverter


class DSNSpeciesImporter:
    """
    Convierte registros de especies de DSN
    al formato oficial de ODIN.
    """

    def __init__(self) -> None:

        self.converter = KnowledgeConverter()

    def convert_species(
        self,
        species: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convierte una especie individual.
        """

        genus = self.converter.normalize_text(
            species.get("genus")
        )

        species_name = self.converter.normalize_text(
            species.get("species")
        )

        variant = self.converter.normalize_text(
            species.get("variant")
        )

        rarity = self.converter.normalize_text(
            species.get("rarity")
        )

        identifier = self.converter.normalize_identifier(
            f"{genus}_{species_name}"
        )

        return {

            "id": identifier,

            "genus": genus,

            "species": species_name,

            "variant": variant,

            "rarity": rarity,

            "source": "Deep Space Network",

            "raw": species,
        }

    def convert_document(
        self,
        document: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Convierte un documento completo.
        """

        records = (
            document.get("species")
            or document.get("records")
            or []
        )

        converted: list[dict[str, Any]] = []

        for item in records:

            converted.append(
                self.convert_species(item)
            )

        return converted