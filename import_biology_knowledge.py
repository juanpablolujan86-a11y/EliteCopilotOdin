"""Genera la biblioteca biológica completa de ODIN desde BioScan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from knowledge.importer.biology_validator import BiologyKnowledgeValidator
from knowledge.importer.bioscan_biology_importer import (
    BioScanBiologyImporter,
)


PROJECT_ROOT = Path(__file__).resolve().parent
RULESETS_DIRECTORY = (
    PROJECT_ROOT
    / "knowledge"
    / "external"
    / "bioscan"
    / "EDMC-BioScan-master"
    / "src"
    / "bio_scan"
    / "bio_data"
    / "rulesets"
)
SPECIES_OUTPUT = PROJECT_ROOT / "knowledge" / "biology" / "species.json"
RULES_OUTPUT = (
    PROJECT_ROOT / "knowledge" / "biology" / "prediction_rules.json"
)


def write_json(path: Path, document: dict[str, Any]) -> None:
    """Escribe JSON legible mediante reemplazo atómico."""

    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(document, file, ensure_ascii=False, indent=4)
        file.write("\n")
    temporary_path.replace(path)


def main() -> None:
    importer = BioScanBiologyImporter(RULESETS_DIRECTORY)
    species, rules = importer.import_all()
    report = BiologyKnowledgeValidator().validate(species, rules)

    if not report.valid:
        raise ValueError(f"Biblioteca biológica inválida: {report}")

    source_files = [path.name for path in importer.source_files()]
    common_metadata = {
        "schema_version": "1.1.0",
        "generated_by": "HUGINN",
        "source": {
            "id": "bioscan",
            "rulesets_directory": str(
                RULESETS_DIRECTORY.relative_to(PROJECT_ROOT)
            ),
            "files": source_files,
        },
    }
    write_json(
        SPECIES_OUTPUT,
        {**common_metadata, "species": species},
    )
    write_json(
        RULES_OUTPUT,
        {**common_metadata, "rules": rules},
    )

    print("HUGINN - Operación Yggdrasil")
    print(f"Géneros importados : {report.genus_count}")
    print(f"Especies importadas: {report.species_count}")
    print(f"Reglas importadas  : {report.rules_count}")
    print(
        "Sin reglas          : "
        + ", ".join(report.species_without_rules)
    )
    print(f"IDs duplicados     : {len(report.duplicate_species_ids)}")
    print(f"Reglas duplicadas  : {len(report.duplicate_rule_ids)}")
    print(f"Referencias rotas  : {len(report.rules_without_species)}")
    print(f"Reglas vacías      : {len(report.empty_rule_ids)}")
    print(f"Biblioteca válida  : {'sí' if report.valid else 'no'}")


if __name__ == "__main__":
    main()
