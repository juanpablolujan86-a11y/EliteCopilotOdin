# ============================================================
# ODIN
#
# Versión : 0.1.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
mimir.planet_event_adapter

Adapta eventos Scan del Journal de Elite Dangerous
al formato planetario utilizado por MÍMIR.
"""

from typing import Any


STANDARD_GRAVITY = 9.80665


class PlanetEventAdapter:
    """
    Convierte un evento Scan del Journal en datos
    normalizados para el análisis científico.
    """

    def from_scan_event(
        self,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convierte un evento Scan en un planeta
        compatible con SpeciesPredictor.
        """

        surface_gravity = event.get(
            "SurfaceGravity"
        )

        gravity = self._convert_gravity(
            surface_gravity
        )

        atmosphere = self._normalize_atmosphere(
            event.get("AtmosphereType")
            or event.get("Atmosphere")
        )

        body_type = self._normalize_text(
            event.get("PlanetClass")
        )

        volcanism = self._normalize_volcanism(
            event.get("Volcanism")
        )

        return {
            "atmosphere": atmosphere,
            "body_type": body_type,
            "gravity": gravity,
            "temperature": event.get(
                "SurfaceTemperature"
            ),
            "volcanism": volcanism,
        }

    def _convert_gravity(
        self,
        value: Any,
    ) -> float | None:
        """
        Convierte gravedad de m/s² a gravedad terrestre.
        """

        if value is None:
            return None

        try:
            gravity_ms2 = float(value)

        except (TypeError, ValueError):
            return None

        return round(
            gravity_ms2 / STANDARD_GRAVITY,
            6,
        )

    def _normalize_atmosphere(
        self,
        value: Any,
    ) -> str | None:
        """
        Normaliza la atmósfera al formato utilizado
        por las reglas de la Enciclopedia.
        """

        text = self._normalize_text(value)

        if text is None:
            return None

        compact = (
            text
            .replace(" atmosphere", "")
            .replace(" rich", "Rich")
            .replace(" ", "")
        )

        mapping = {
            "carbondioxide": "CarbonDioxide",
            "carbondioxiderich": "CarbonDioxideRich",
            "sulphurdioxide": "SulphurDioxide",
            "ammonia": "Ammonia",
            "argon": "Argon",
            "argonrich": "ArgonRich",
            "oxygen": "Oxygen",
            "water": "Water",
            "none": "None",
        }

        return mapping.get(
            compact.lower(),
            compact,
        )

    def _normalize_volcanism(
        self,
        value: Any,
    ) -> str:
        """
        Normaliza la información de volcanismo.
        """

        text = self._normalize_text(value)

        if not text:
            return "None"

        if text.lower() in {
            "none",
            "no volcanism",
        }:
            return "None"

        return text

    def _normalize_text(
        self,
        value: Any,
    ) -> str | None:
        """
        Convierte un valor en texto limpio.
        """

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        return text