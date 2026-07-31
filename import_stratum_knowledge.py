"""
import_stratum_knowledge.py

Importa el catálogo real de Stratum desde la copia local
de EDMC BioScan y genera conocimiento normalizado para ODIN.
"""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

from knowledge.importer.stratum_importer import StratumImporter


PROJECT_ROOT = Path(__file__).resolve().parent

SOURCE_FILE = (
    PROJECT_ROOT
    / "knowledge"
    / "external"
    / "bioscan"
    / "EDMC-BioScan-master"
    / "src"
    / "bio_scan"
    / "bio_data"
    / "rulesets"
    / "stratum.py"
)

SPECIES_OUTPUT = (
    PROJECT_ROOT
    / "knowledge"
    / "biology"
    / "species.json"
)

RULES_OUTPUT = (
    PROJECT_ROOT
    / "knowledge"
    / "biology"
    / "prediction_rules.json"
)


def load_python_module(
    module_path: Path,
) -> ModuleType:
    """
    Carga un archivo Python externo como módulo,
    sin modificarlo ni copiar su código.
    """

    if not module_path.exists():
        raise FileNotFoundError(
            f"No se encontró la fuente:\n{module_path}"
        )

    specification = importlib.util.spec_from_file_location(
        "external_bioscan_stratum",
        module_path,
    )

    if (
        specification is None
        or specification.loader is None
    ):
        raise ImportError(
            f"No se pudo preparar el módulo:\n{module_path}"
        )

    module = importlib.util.module_from_spec(
        specification
    )

    specification.loader.exec_module(module)

    return module


def write_json(
    output_path: Path,
    document: dict[str, Any],
) -> None:
    """
    Escribe un documento JSON con formato legible.
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            document,
            output_file,
            ensure_ascii=False,
            indent=4,
        )


def main() -> None:
    print("=" * 60)
    print("HUGINN - Importación de conocimiento Stratum")
    print("=" * 60)

    module = load_python_module(
        SOURCE_FILE
    )

    catalog = getattr(
        module,
        "catalog",
        None,
    )

    if not isinstance(catalog, dict):
        raise ValueError(
            "El archivo externo no contiene "
            "un catálogo válido."
        )

    importer = StratumImporter()

    species, rules = importer.convert(
        catalog
    )

    species_document = {
        "schema_version": "1.0.0",
        "generated_by": "HUGINN",
        "source": {
            "id": "bioscan",
            "file": str(
                SOURCE_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),
        },
        "species": species,
    }

    rules_document = {
        "schema_version": "1.0.0",
        "generated_by": "HUGINN",
        "source": {
            "id": "bioscan",
            "file": str(
                SOURCE_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),
        },
        "rules": rules,
    }

    write_json(
        SPECIES_OUTPUT,
        species_document,
    )

    write_json(
        RULES_OUTPUT,
        rules_document,
    )

    print()
    print(
        f"Especies importadas : {len(species)}"
    )
    print(
        f"Reglas importadas   : {len(rules)}"
    )
    print()
    print(
        "Archivo de especies : "
        f"{SPECIES_OUTPUT.relative_to(PROJECT_ROOT)}"
    )
    print(
        "Archivo de reglas   : "
        f"{RULES_OUTPUT.relative_to(PROJECT_ROOT)}"
    )
    print()
    print(
        "Importación completada correctamente."
    )


if __name__ == "__main__":
    main()