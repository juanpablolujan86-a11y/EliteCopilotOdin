"""
knowledge.importer.stratum_importer

Importador del género Stratum para HUGINN.

Lee el catálogo de BioScan y genera el formato
interno de la Enciclopedia Galáctica de ODIN.
"""

from typing import Any


class StratumImporter:

    def convert(
        self,
        catalog: dict[str, Any],
    ) -> tuple[list[dict], list[dict]]:

        species = []

        rules = []

        for genus in catalog.values():

            for codex_id, data in genus.items():

                species_id = (
                    data["name"]
                    .lower()
                    .replace(" ", "_")
                )

                species.append(
                    {
                        "id": species_id,
                        "name": data["name"],
                        "genus": "Stratum",
                        "value": data.get(
                            "value",
                            0,
                        ),
                    }
                )

                for index, rule in enumerate(
                    data.get(
                        "rulesets",
                        [],
                    ),
                    start=1,
                ):

                    rules.append(
                        {
                            "species": species_id,
                            "rule_id": f"{species_id}_{index}",
                            "conditions": rule,
                        }
                    )

        return species, rules