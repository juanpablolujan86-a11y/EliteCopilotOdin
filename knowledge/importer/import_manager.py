"""
knowledge.importer.import_manager

HUGINN

Coordinador del proceso de adquisición de conocimiento.
"""

from pathlib import Path
import json
from typing import Any

from knowledge.importer.converter import KnowledgeConverter
from knowledge.importer.source_manifest import SourceManifest
from knowledge.importer.validator import KnowledgeValidator
from knowledge.importer.providers.dsn_provider import DeepSpaceNetworkProvider

class ImportManager:

    def __init__(self) -> None:

        self.manifest = SourceManifest()
        self.validator = KnowledgeValidator()
        self.converter = KnowledgeConverter()
        self.providers = {
            "dsn": DeepSpaceNetworkProvider(),
        }

    def available_sources(self) -> list[str]:

        return [
            source.id
            for source in self.manifest.get_sources()
        ]

    def has_source(
        self,
        source_id: str,
    ) -> bool:

        return self.manifest.has(source_id)

    def validate_source(
        self,
        source_id: str,
    ) -> tuple[bool, list[str]]:

        source = self.manifest.get(source_id)

        return self.validator.validate_source(source)

    def load_json_file(
        self,
        file_path: str,
    ) -> dict[str, Any]:

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(path)

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    def inspect_file(
        self,
        file_path: str,
    ) -> dict[str, Any]:

        document = self.load_json_file(file_path)

        valid, errors = (
            self.validator.validate_json_document(
                document
            )
        )

        source = document.get(
            "source",
            "unknown",
        )

        records = document.get(
            "species",
            document.get(
                "records",
                [],
            ),
        )

        return {
            "valid": valid,
            "errors": errors,
            "source": source,
            "record_count": len(records),
            "document": document,
        }
    def get_provider(
        self,
        source_id: str,
    ):
        """
        Devuelve el proveedor correspondiente.
        """

        return self.providers.get(source_id)

    def inspect_with_provider(
        self,
        source_id: str,
        file_path: str,
    ) -> dict:

        provider = self.get_provider(source_id)

        if provider is None:
            raise ValueError(
                f"Proveedor desconocido: {source_id}"
            )

        return provider.inspect(
            Path(file_path)
        )