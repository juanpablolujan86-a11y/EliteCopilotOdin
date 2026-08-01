"""Importación completa de reglas biológicas de EDMC BioScan."""

from __future__ import annotations

import importlib.util
import re
import unicodedata
from pathlib import Path
from types import ModuleType
from typing import Any


GENUS_NAMES = {
    "aleoida": "Aleoida",
    "anemone": "Anemone",
    "bacterium": "Bacterium",
    "brain_tree": "Brain Tree",
    "cactoida": "Cactoida",
    "clypeus": "Clypeus",
    "concha": "Concha",
    "electricae": "Electricae",
    "fonticulua": "Fonticulua",
    "frutexa": "Frutexa",
    "fumerola": "Fumerola",
    "fungoida": "Fungoida",
    "osseus": "Osseus",
    "recepta": "Recepta",
    "shard": "Crystalline Shards",
    "stratum": "Stratum",
    "tubers": "Sinuous Tubers",
    "tubus": "Tubus",
    "tussock": "Tussock",
}


def slugify(value: str) -> str:
    """Genera un identificador estable a partir de un nombre."""

    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")


def json_compatible(value: Any) -> Any:
    """Normaliza estructuras Python al modelo de datos de JSON."""

    if isinstance(value, dict):
        return {
            key: json_compatible(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [json_compatible(item) for item in value]
    return value


class BioScanBiologyImporter:
    """Convierte todos los catálogos biológicos de BioScan a ODIN."""

    def __init__(self, rulesets_directory: Path) -> None:
        self.rulesets_directory = rulesets_directory

    def source_files(self) -> list[Path]:
        """Devuelve los catálogos reconocidos en orden estable."""

        files = [
            path
            for path in self.rulesets_directory.glob("*.py")
            if path.stem in GENUS_NAMES
        ]
        return sorted(files, key=lambda path: path.name)

    def import_all(self) -> tuple[list[dict], list[dict]]:
        """Importa todas las especies y reglas disponibles."""

        species: list[dict] = []
        rules: list[dict] = []

        for source_file in self.source_files():
            module = self._load_module(source_file)
            catalog = getattr(module, "catalog", None)
            if not isinstance(catalog, dict):
                raise ValueError(
                    f"Catálogo inválido en {source_file}"
                )

            converted_species, converted_rules = self._convert_catalog(
                catalog=catalog,
                genus=GENUS_NAMES[source_file.stem],
                source_file=source_file.name,
            )
            species.extend(converted_species)
            rules.extend(converted_rules)

        species.sort(key=lambda item: item["id"])
        rules.sort(key=lambda item: item["rule_id"])
        return species, rules

    def _convert_catalog(
        self,
        catalog: dict[str, Any],
        genus: str,
        source_file: str,
    ) -> tuple[list[dict], list[dict]]:
        species: list[dict] = []
        rules: list[dict] = []

        for genus_codex_id, genus_catalog in catalog.items():
            if not isinstance(genus_catalog, dict):
                raise ValueError(
                    f"Grupo inválido en {source_file}"
                )

            for codex_id, data in genus_catalog.items():
                if not isinstance(data, dict):
                    raise ValueError(
                        f"Especie inválida {codex_id} en {source_file}"
                    )

                name = data.get("name")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(
                        f"Nombre inválido {codex_id} en {source_file}"
                    )

                species_id = slugify(name)
                species.append(
                    {
                        "id": species_id,
                        "name": name,
                        "genus": genus,
                        "genus_codex_id": genus_codex_id,
                        "value": int(data.get("value", 0)),
                        "codex_id": codex_id,
                        "source_file": source_file,
                    }
                )

                for index, conditions in enumerate(
                    data.get("rulesets", []),
                    start=1,
                ):
                    if not isinstance(conditions, dict):
                        raise ValueError(
                            f"Regla inválida para {name} en {source_file}"
                        )
                    rules.append(
                        {
                            "species": species_id,
                            "rule_id": f"{species_id}_{index}",
                            "conditions": json_compatible(conditions),
                            "source_file": source_file,
                        }
                    )

        return species, rules

    @staticmethod
    def _load_module(module_path: Path) -> ModuleType:
        module_name = f"odin_bioscan_{module_path.stem}"
        specification = importlib.util.spec_from_file_location(
            module_name,
            module_path,
        )
        if specification is None or specification.loader is None:
            raise ImportError(f"No se pudo cargar {module_path}")

        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module
