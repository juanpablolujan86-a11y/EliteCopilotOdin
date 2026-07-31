# ============================================================
# ODIN
#
# Versión : 0.2.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
Prueba de MÍMIR utilizando un evento Scan real
del Journal de Elite Dangerous.

Busca el Journal más reciente, localiza el último
escaneo planetario y lo envía al OfficerDispatcher.
"""

import json
from pathlib import Path
from typing import Any

from core.officer_dispatcher import OfficerDispatcher
from mimir.officer_handler import MimirOfficerHandler
from mimir.scientific_officer import ScientificOfficer


ROOT = Path(__file__).resolve().parent

JOURNAL_DIRECTORY = (
    Path.home()
    / "Saved Games"
    / "Frontier Developments"
    / "Elite Dangerous"
)

SPECIES_FILE = (
    ROOT
    / "knowledge"
    / "biology"
    / "species.json"
)

RULES_FILE = (
    ROOT
    / "knowledge"
    / "biology"
    / "prediction_rules.json"
)


def translate_priority(
    priority: str,
) -> str:
    """
    Convierte una prioridad interna en una
    descripción natural para el comandante.
    """

    priorities = {
        "LOW": "Bajo",
        "MEDIUM": "Moderado",
        "HIGH": "Muy alto",
        "CRITICAL": "Crítico",
    }

    return priorities.get(
        priority,
        priority,
    )


def find_latest_journal() -> Path:
    """
    Devuelve el archivo Journal más reciente.
    """

    journals = sorted(
        JOURNAL_DIRECTORY.glob(
            "Journal.*.log"
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not journals:
        raise FileNotFoundError(
            "No se encontraron archivos Journal en:\n"
            f"{JOURNAL_DIRECTORY}"
        )

    return journals[0]


def find_latest_planet_scan(
    journal_path: Path,
) -> dict[str, Any] | None:
    """
    Busca el último evento Scan planetario válido.
    """

    latest_scan: dict[str, Any] | None = None

    with journal_path.open(
        "r",
        encoding="utf-8",
    ) as journal:
        for line_number, line in enumerate(
            journal,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            try:
                event = json.loads(line)

            except json.JSONDecodeError:
                print(
                    "Advertencia: línea inválida "
                    f"ignorada ({line_number})."
                )
                continue

            if event.get("event") != "Scan":
                continue

            if not event.get("PlanetClass"):
                continue

            latest_scan = event

    return latest_scan


def main() -> None:
    print("=" * 60)
    print("ODIN - MÍMIR Real Journal Test")
    print("=" * 60)

    journal_path = find_latest_journal()

    print()
    print(
        "Journal seleccionado:",
        journal_path.name,
    )

    scan_event = find_latest_planet_scan(
        journal_path
    )

    if scan_event is None:
        print()
        print(
            "No se encontró ningún evento Scan "
            "planetario en el Journal."
        )
        return

    print()
    print(
        "Cuerpo encontrado:",
        scan_event.get(
            "BodyName",
            "Desconocido",
        ),
    )

    mimir = ScientificOfficer(
        species_file=SPECIES_FILE,
        rules_file=RULES_FILE,
    )

    handler = MimirOfficerHandler(
        mimir
    )

    dispatcher = OfficerDispatcher()

    dispatcher.register(
        "planet_scan",
        handler.handle_planet_scan,
    )

    reports = dispatcher.dispatch(
        "planet_scan",
        scan_event,
    )

    print()
    print(
        "Informes generados:",
        len(reports),
    )

    for report in reports:
        print()
        print("=" * 60)
        print(report.officer)
        print("=" * 60)

        print()
        print(report.title)

        print()
        print(report.message)

        print()
        print(
            "Interés científico:",
            translate_priority(
                report.priority
            ),
        )

        print()
        print("Detalles:")

        for detail in report.details:
            print(
                f"  - {detail}"
            )


if __name__ == "__main__":
    main()