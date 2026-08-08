# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
models.officer_report

Modelo común utilizado por todos los oficiales de ODIN
para informar resultados al comandante.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class OfficerReport:
    """
    Informe emitido por cualquier oficial.
    """

    officer: str

    title: str

    message: str

    priority: str

    details: list[str]

    body_name: str = ""

    confirmed_genus_names: tuple[str, ...] = ()

    probable_species: tuple[str, ...] = ()

    # (nombre, valor base, valor potencial First Logged)
    probable_species_values: tuple[tuple[str, int, int], ...] = ()

    has_biological_signal: bool = False
