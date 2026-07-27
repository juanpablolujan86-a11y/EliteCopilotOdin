"""
knowledge.importer.source_manifest

Registro oficial de las fuentes de conocimiento
utilizadas por ODIN.

Este módulo no descarga información.

Su única responsabilidad es describir las fuentes
que el sistema puede importar.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class KnowledgeSource:

    id: str

    name: str

    description: str

    homepage: str

    license: str

    enabled: bool = True


class SourceManifest:
    """
    Registro de fuentes de conocimiento.
    """

    def __init__(self) -> None:

        self._sources: Dict[str, KnowledgeSource] = {

            "bioscan": KnowledgeSource(

                id="bioscan",

                name="EDMC BioScan",

                description="Predicción de especies y datos exobiológicos.",

                homepage="https://github.com/Silarn/EDMC-BioScan",

                license="GPL-2.0",

            ),

            "canonn": KnowledgeSource(

                id="canonn",

                name="Canonn Research",

                description="Investigación científica de Elite Dangerous.",

                homepage="https://canonn.science",

                license="Community",

            ),

            "dsn": KnowledgeSource(

                id="dsn",

                name="Deep Space Network",

                description="Condiciones de aparición de especies.",

                homepage="https://ed-dsn.net",

                license="Community",

            ),

            "edsm": KnowledgeSource(

                id="edsm",

                name="Elite Dangerous Star Map",

                description="Información galáctica.",

                homepage="https://www.edsm.net",

                license="Community",

            ),

            "spansh": KnowledgeSource(

                id="spansh",

                name="Spansh",

                description="Herramientas de navegación.",

                homepage="https://www.spansh.co.uk",

                license="Community",

            ),
        }

    def get_sources(self) -> list[KnowledgeSource]:
        """
        Devuelve todas las fuentes registradas.
        """

        return list(self._sources.values())

    def get(self, source_id: str) -> KnowledgeSource | None:
        """
        Devuelve una fuente por su identificador.
        """

        return self._sources.get(source_id)

    def has(self, source_id: str) -> bool:
        """
        Indica si una fuente está registrada.
        """

        return source_id in self._sources