"""
knowledge.importer.providers.dsn_provider

Proveedor de conocimiento para Deep Space Network.
"""

from pathlib import Path
import json
from typing import Any

from knowledge.importer.providers.base_provider import (
    BaseKnowledgeProvider,
)


class DeepSpaceNetworkProvider(BaseKnowledgeProvider):
    """
    Primer proveedor de conocimiento para HUGINN.
    """

    @property
    def source_id(self) -> str:
        return "dsn"

    @property
    def source_name(self) -> str:
        return "Deep Space Network"

    def inspect(
        self,
        path: Path,
    ) -> dict[str, Any]:
        """
        Inspecciona un documento JSON sin modificarlo.
        """

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            document = json.load(file)

        records = (
            document.get("species")
            or document.get("records")
            or []
        )

        return {
            "provider": self.source_name,
            "source_id": self.source_id,
            "valid": True,
            "record_count": len(records),
            "fields": sorted(document.keys()),
            "document": document,
        }

    def import_data(
        self,
        path: Path,
    ) -> dict[str, Any]:
        """
        Devuelve el documento completo para que el
        importador específico lo procese.
        """

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)