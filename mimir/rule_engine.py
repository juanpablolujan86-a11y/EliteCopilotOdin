"""
mimir.rule_engine

Motor de evaluación de reglas científicas de MÍMIR.

Una regla representa un conjunto completo de condiciones
de aparición. Si una condición declarada no coincide,
la regla se considera incompatible.
"""

from typing import Any


class RuleEngine:
    """
    Evalúa si un planeta cumple una regla biológica.
    """

    SUPPORTED_CONDITIONS = {
        "atmosphere",
        "body_type",
        "max_gravity",
        "max_pressure",
        "max_temperature",
        "min_gravity",
        "min_pressure",
        "min_temperature",
        "regions",
        "volcanism",
    }

    def evaluate(
        self,
        planet: dict[str, Any],
        rule: dict[str, Any],
    ) -> tuple[int, list[str]]:
        """
        Devuelve el porcentaje de coincidencia y las
        condiciones cumplidas.

        Si una condición requerida falla, devuelve 0.
        """

        unsupported = set(rule) - self.SUPPORTED_CONDITIONS
        if unsupported:
            return 0, []

        checks: list[tuple[str, bool]] = []

        if "atmosphere" in rule:
            checks.append(
                (
                    "Atmosphere",
                    planet.get("atmosphere")
                    in rule["atmosphere"],
                )
            )

        if "body_type" in rule:
            checks.append(
                (
                    "Body Type",
                    planet.get("body_type")
                    in rule["body_type"],
                )
            )

        if "min_gravity" in rule:
            gravity = planet.get("gravity")

            checks.append(
                (
                    "Minimum Gravity",
                    gravity is not None
                    and gravity >= rule["min_gravity"],
                )
            )

        if "max_gravity" in rule:
            gravity = planet.get("gravity")

            checks.append(
                (
                    "Maximum Gravity",
                    gravity is not None
                    and gravity <= rule["max_gravity"],
                )
            )

        if "min_temperature" in rule:
            temperature = planet.get("temperature")

            checks.append(
                (
                    "Minimum Temperature",
                    temperature is not None
                    and temperature
                    >= rule["min_temperature"],
                )
            )

        if "max_temperature" in rule:
            temperature = planet.get("temperature")

            checks.append(
                (
                    "Maximum Temperature",
                    temperature is not None
                    and temperature
                    <= rule["max_temperature"],
                )
            )

        if "min_pressure" in rule:
            pressure = planet.get("pressure")

            checks.append(
                (
                    "Minimum Pressure",
                    pressure is not None
                    and pressure >= rule["min_pressure"],
                )
            )

        if "max_pressure" in rule:
            pressure = planet.get("pressure")

            checks.append(
                (
                    "Maximum Pressure",
                    pressure is not None
                    and pressure <= rule["max_pressure"],
                )
            )

        if "volcanism" in rule:
            expected = rule["volcanism"]
            actual = planet.get("volcanism")

            actual_text = "" if actual in (None, "None") else str(actual)
            actual_normalized = actual_text.lower()

            if isinstance(expected, list):
                volcanism_matches = any(
                    (
                        actual_normalized == item[1:].lower()
                        if item.startswith("=")
                        else item.lower() in actual_normalized
                    )
                    for item in expected
                )
            elif expected == "Any":
                volcanism_matches = bool(actual_normalized)
            elif expected == "None":
                volcanism_matches = not actual_normalized
            elif expected.startswith("!"):
                volcanism_matches = (
                    bool(actual_normalized)
                    and expected[1:].lower() not in actual_normalized
                )
            else:
                volcanism_matches = expected.lower() in actual_normalized

            checks.append(
                (
                    "Volcanism",
                    volcanism_matches,
                )
            )

        if "regions" in rule:
            region = planet.get("region")

            included_regions = {
                item
                for item in rule["regions"]
                if not item.startswith("!")
            }
            excluded_regions = {
                item.removeprefix("!")
                for item in rule["regions"]
                if item.startswith("!")
            }

            region_matches = (
                region is not None
                and region not in excluded_regions
                and (
                    not included_regions
                    or region in included_regions
                )
            )

            checks.append(
                (
                    "Region",
                    region_matches,
                )
            )

        if not checks:
            return 0, []

        failed = [
            name
            for name, matched in checks
            if not matched
        ]

        if failed:
            return 0, []

        matches = [
            name
            for name, matched in checks
            if matched
        ]

        return 100, matches
