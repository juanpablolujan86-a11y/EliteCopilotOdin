# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 5 - Integración
# ============================================================

"""
planet_scan_ready.py

Evento interno emitido cuando un planeta ha sido
registrado por ExplorationProcessor y está listo
para ser analizado por los oficiales científicos.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PlanetScanReady:
    """
    Evento interno para análisis científico.
    """

    event: dict[str, Any]

    confirmed_genus_ids: tuple[str, ...] = ()

    confirmed_genus_names: tuple[str, ...] = ()
