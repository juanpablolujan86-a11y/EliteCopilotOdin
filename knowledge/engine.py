"""
knowledge.engine

Puerta de entrada a la Biblioteca del Conocimiento de ODIN.
"""

from typing import Any

from knowledge.loader import KnowledgeLoader
from knowledge.models import DomainCatalog, KnowledgeSource


class KnowledgeEngine:
    """
    Proporciona acceso controlado al conocimiento de ODIN.
    """

    def __init__(self) -> None:
        self.loader = KnowledgeLoader()
        self._knowledge: dict[str, Any] = {}

    def load(self) -> None:
        """
        Carga toda la Biblioteca del Conocimiento en memoria.
        """

        self._knowledge = self.loader.load()

    def get_domains(self) -> list[str]:
        """
        Devuelve los dominios disponibles.
        """

        return list(self._knowledge.keys())

    def has_domain(self, domain: str) -> bool:
        """
        Indica si un dominio está disponible.
        """

        return domain in self._knowledge

    def get_domain(
        self,
        domain: str,
    ) -> dict[str, Any]:
        """
        Devuelve el contenido completo de un dominio.
        """

        return self._knowledge.get(domain, {})

    def get_catalog(
        self,
        domain: str,
    ) -> DomainCatalog | None:
        """
        Devuelve el catálogo tipado de un dominio.
        """

        domain_data = self.get_domain(domain)
        catalog_data = domain_data.get("catalog")

        if not catalog_data:
            return None

        sources = [
            KnowledgeSource(
                name=source.get("name", ""),
                reference=source.get("reference", ""),
                last_verified=source.get(
                    "last_verified",
                    "",
                ),
            )
            for source in catalog_data.get("sources", [])
        ]

        return DomainCatalog(
            domain=catalog_data.get("domain", domain),
            name=catalog_data.get("name", domain),
            version=catalog_data.get("version", "0.0.0"),
            status=catalog_data.get("status", "unknown"),
            sources=sources,
        )

    def count_resources(
        self,
        domain: str,
    ) -> int:
        """
        Cuenta los archivos de conocimiento cargados
        dentro de un dominio.
        """

        return len(self.get_domain(domain))

    def is_loaded(self) -> bool:
        """
        Indica si la biblioteca ya fue cargada.
        """

        return bool(self._knowledge)