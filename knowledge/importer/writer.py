"""
knowledge.importer.writer

Escritura de documentos normalizados
de la Biblioteca del Conocimiento.
"""

from pathlib import Path
import json
from typing import Any


class KnowledgeWriter:

    def write_json(
        self,
        path: str,
        document: dict[str, Any],
    ) -> None:

        file = Path(path)

        file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with file.open(
            "w",
            encoding="utf-8",
        ) as output:

            json.dump(
                document,
                output,
                indent=4,
                ensure_ascii=False,
            )

    def write_species(
        self,
        path: str,
        species: list[dict[str, Any]],
    ) -> None:

        document = {

            "schema_version": "1.0",

            "generated_by": "HUGINN",

            "species": species,
        }

        self.write_json(
            path,
            document,
        )