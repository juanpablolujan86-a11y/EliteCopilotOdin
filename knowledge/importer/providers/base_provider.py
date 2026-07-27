"""
knowledge.importer.providers.base_provider

Clase base para todos los proveedores de conocimiento
utilizados por HUGINN.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseKnowledgeProvider(ABC):
    """
    Contrato que deberán implementar todos los
    proveedores de conocimiento.
    """

    @property
    @abstractmethod
    def source_id(self) -> str:
        """
        Identificador de la fuente.
        """
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """
        Nombre de la fuente.
        """
        ...

    @abstractmethod
    def inspect(
        self,
        path: Path,
    ) -> dict[str, Any]:
        """
        Inspecciona un archivo y devuelve un informe.
        """
        ...

    @abstractmethod
    def import_data(
        self,
        path: Path,
    ) -> dict[str, Any]:
        """
        Convierte un archivo al formato interno de ODIN.
        """
        ...