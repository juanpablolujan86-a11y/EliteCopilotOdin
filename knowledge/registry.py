"""
knowledge.registry

Registro central de la Biblioteca del Conocimiento de ODIN.

Su responsabilidad es conocer qué dominios existen
y dónde se encuentran dentro del proyecto.
"""

from pathlib import Path


class KnowledgeRegistry:
    """
    Registro de dominios de conocimiento.
    """

    def __init__(self) -> None:
        base_path = Path(__file__).parent

        self._domains = {
            "biology": base_path / "biology",
            "geology": base_path / "geology",
            "astronomy": base_path / "astronomy",
            "economy": base_path / "economy",
        }

    def get_domains(self) -> list[str]:
        """
        Devuelve la lista de dominios registrados.
        """
        return list(self._domains.keys())

    def get_domain_path(self, domain: str) -> Path:
        """
        Devuelve la carpeta correspondiente a un dominio.
        """
        return self._domains[domain]

    def has_domain(self, domain: str) -> bool:
        """
        Indica si el dominio solicitado existe.
        """
        return domain in self._domains