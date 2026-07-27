"""
knowledge.importer.validator

Valida fuentes y datos antes de incorporarlos
a la Biblioteca del Conocimiento de ODIN.
"""

from typing import Any

from knowledge.importer.source_manifest import KnowledgeSource


class KnowledgeValidator:
    """
    Comprueba que las fuentes y los datos importados
    tengan una estructura válida.
    """

    def validate_source(
        self,
        source: KnowledgeSource | None,
    ) -> tuple[bool, list[str]]:
        """
        Valida la información básica de una fuente.
        """

        errors: list[str] = []

        if source is None:
            errors.append("La fuente no existe.")
            return False, errors

        if not source.id.strip():
            errors.append(
                "La fuente no tiene identificador."
            )

        if not source.name.strip():
            errors.append(
                "La fuente no tiene nombre."
            )

        if not source.homepage.strip():
            errors.append(
                "La fuente no tiene página oficial."
            )

        if not source.license.strip():
            errors.append(
                "La fuente no tiene licencia registrada."
            )

        if not source.enabled:
            errors.append(
                "La fuente está deshabilitada."
            )

        return len(errors) == 0, errors

    def validate_json_document(
        self,
        document: Any,
    ) -> tuple[bool, list[str]]:
        """
        Comprueba que un documento JSON tenga
        una estructura básica aceptable.
        """

        errors: list[str] = []

        if not isinstance(document, dict):
            errors.append(
                "El documento raíz debe ser un objeto JSON."
            )

            return False, errors

        if not document:
            errors.append(
                "El documento JSON está vacío."
            )

        return len(errors) == 0, errors