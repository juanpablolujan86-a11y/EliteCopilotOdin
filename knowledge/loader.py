"""
knowledge.loader

Carga los archivos JSON de la Biblioteca del Conocimiento de ODIN.
"""

import json
from pathlib import Path
from typing import Any

from knowledge.registry import KnowledgeRegistry


class KnowledgeLoader:
    """
    Carga todos los dominios registrados en memoria.
    """

    def __init__(self) -> None:
        self.registry = KnowledgeRegistry()

    def load(self) -> dict[str, Any]:
        """
        Carga todos los dominios registrados.
        """

        knowledge: dict[str, Any] = {}

        for domain in self.registry.get_domains():
            knowledge[domain] = self._load_domain(domain)

        return knowledge

    def _load_domain(self, domain: str) -> dict[str, Any]:
        """
        Carga todos los archivos JSON de un dominio.
        """

        domain_path = self.registry.get_domain_path(domain)

        if not domain_path.exists():
            return {}

        domain_data: dict[str, Any] = {}

        for json_file in domain_path.rglob("*.json"):
            relative_path = json_file.relative_to(domain_path)
            key = relative_path.with_suffix("").as_posix()

            try:
                with json_file.open(
                    "r",
                    encoding="utf-8",
                ) as file:
                    domain_data[key] = json.load(file)

            except json.JSONDecodeError as error:
                print(
                    "KnowledgeLoader      : "
                    f"JSON inválido en {json_file.name}: {error}"
                )

            except OSError as error:
                print(
                    "KnowledgeLoader      : "
                    f"No se pudo leer {json_file.name}: {error}"
                )

        return domain_data