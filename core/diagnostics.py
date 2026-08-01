"""Registro persistente de funcionamiento y actividad científica."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.version import CAPABILITY, VERSION
from models.events.organic_scan_updated import OrganicScanUpdated
from models.officer_report import OfficerReport


def _handler(path: Path) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    return handler


def configure_diagnostics(data_root: Path) -> None:
    """Configura los archivos de diagnóstico una sola vez."""

    logs = data_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(getattr(item, "baseFilename", None) for item in root.handlers):
        root.addHandler(_handler(logs / "odin.log"))

    logging.getLogger("odin").info(
        "Inicio de ODIN v%s - %s", VERSION, CAPABILITY
    )


def log_fatal_error() -> None:
    logging.getLogger("odin").exception("Fallo fatal no controlado")


class MimirDiagnostics:
    """Guarda un historial humano de lo que MÍMIR decidió y observó."""

    def __init__(self, data_root: Path) -> None:
        logs = data_root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("mimir.activity")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            self.logger.addHandler(_handler(logs / "mimir.log"))

    def record_scientific_report(self, report: OfficerReport) -> None:
        details = " | ".join(report.details) if report.details else "Sin detalles"
        self.logger.info(
            "ANÁLISIS | prioridad=%s | título=%s | mensaje=%s | %s",
            report.priority,
            report.title,
            report.message,
            details,
        )

    def record_organic_scan(self, scan: OrganicScanUpdated) -> None:
        self.logger.info(
            "MUESTREO | body_id=%s | género=%s | especie=%s "
            "| variante=%s | progreso=%s/3 | completado=%s | was_logged=%s",
            scan.body_id,
            scan.genus or "",
            scan.species or "",
            scan.variant or "",
            scan.progress,
            scan.completed,
            scan.was_logged,
        )

    def close(self) -> None:
        """Cierra los archivos; se usa en pruebas y apagados controlados."""

        for handler in list(self.logger.handlers):
            handler.close()
            self.logger.removeHandler(handler)
