"""
knowledge.importer.converter

Convierte datos externos al formato interno
de la Biblioteca del Conocimiento de ODIN.
"""

from typing import Any


class KnowledgeConverter:
    """
    Normaliza documentos importados para que ODIN
    trabaje siempre con una estructura consistente.
    """

    def normalize_text(
        self,
        value: Any,
    ) -> str:
        """
        Convierte un valor en texto limpio.
        """

        if value is None:
            return ""

        return str(value).strip()

    def normalize_identifier(
        self,
        value: Any,
    ) -> str:
        """
        Convierte un nombre en un identificador estable.

        Ejemplo:
        'Stratum Tectonicas' -> 'stratum_tectonicas'
        """

        text = self.normalize_text(value).lower()

        replacements = {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ü": "u",
            "ñ": "n",
        }

        for original, replacement in replacements.items():
            text = text.replace(
                original,
                replacement,
            )

        characters: list[str] = []

        previous_was_separator = False

        for character in text:
            if character.isalnum():
                characters.append(character)
                previous_was_separator = False

            elif not previous_was_separator:
                characters.append("_")
                previous_was_separator = True

        return "".join(characters).strip("_")

    def normalize_number(
        self,
        value: Any,
        default: float = 0.0,
    ) -> float:
        """
        Convierte un valor numérico a float.
        """

        if value is None:
            return default

        if isinstance(value, str):
            value = value.replace(",", ".").strip()

        try:
            return float(value)

        except (TypeError, ValueError):
            return default

    def normalize_integer(
        self,
        value: Any,
        default: int = 0,
    ) -> int:
        """
        Convierte un valor numérico a entero.
        """

        try:
            return int(
                self.normalize_number(
                    value,
                    float(default),
                )
            )

        except (TypeError, ValueError):
            return default

    def normalize_string_list(
        self,
        value: Any,
    ) -> list[str]:
        """
        Convierte diferentes formatos en una lista
        limpia y sin elementos repetidos.
        """

        if value is None:
            return []

        if isinstance(value, str):
            values = [
                item.strip()
                for item in value.split(",")
            ]

        elif isinstance(value, list):
            values = [
                self.normalize_text(item)
                for item in value
            ]

        else:
            values = [
                self.normalize_text(value)
            ]

        normalized: list[str] = []

        for item in values:
            if item and item not in normalized:
                normalized.append(item)

        return normalized

    def normalize_source_document(
        self,
        source_id: str,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Crea el contenedor básico de un documento
        normalizado por ODIN.

        La conversión específica de especies se
        agregará cuando integremos la primera fuente.
        """

        return {
            "source_id": self.normalize_identifier(
                source_id
            ),
            "schema_version": "1.0",
            "records": [],
            "metadata": {
                "original_fields": sorted(
                    document.keys()
                ),
            },
        }