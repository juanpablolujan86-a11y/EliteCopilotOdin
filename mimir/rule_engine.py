"""
mimir.rule_engine

Motor de evaluación de reglas científicas de MÍMIR.

Una regla representa un conjunto completo de condiciones
de aparición. Si una condición declarada no coincide,
la regla se considera incompatible.
"""

from typing import Any

from mimir.galactic_region import (
    GUARDIAN_ZONES,
    REGION_GROUPS,
    TUBER_ZONES,
    system_distance,
    is_near_nebula,
)


class RuleEngine:
    """
    Evalúa si un planeta cumple una regla biológica.
    """

    SUPPORTED_CONDITIONS = {
        "atmosphere",
        "atmosphere_component",
        "body_type",
        "max_gravity",
        "max_pressure",
        "max_temperature",
        "min_gravity",
        "min_pressure",
        "min_temperature",
        "regions",
        "max_orbital_period",
        "distance",
        "star",
        "parent_star",
        "guardian",
        "tuber",
        "bodies",
        "region",
        "nebula",
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
            expected_atmosphere = rule["atmosphere"]
            atmosphere = planet.get("atmosphere")
            checks.append(
                (
                    "Atmosphere",
                    (
                        atmosphere not in (None, "None")
                        if expected_atmosphere == "Any"
                        else atmosphere in expected_atmosphere
                    ),
                )
            )

        if "atmosphere_component" in rule:
            composition = planet.get("atmosphere_composition", {})
            checks.append(
                (
                    "Atmosphere Composition",
                    all(
                        float(composition.get(gas, 0)) >= float(percent)
                        for gas, percent in rule[
                            "atmosphere_component"
                        ].items()
                    ),
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
            region_id = planet.get("region_id")
            legacy_region = planet.get("region")

            included_regions = {
                region
                for item in rule["regions"]
                if not item.startswith("!")
                for region in REGION_GROUPS.get(item, [])
            }
            excluded_regions = {
                region
                for item in rule["regions"]
                if item.startswith("!")
                for region in REGION_GROUPS.get(
                    item.removeprefix("!"),
                    [],
                )
            }

            region_matches = (
                (
                    region_id is not None
                    and region_id not in excluded_regions
                    and (
                        not included_regions
                        or region_id in included_regions
                    )
                )
                or (
                    region_id is None
                    and legacy_region is not None
                    and legacy_region not in {
                        item.removeprefix("!")
                        for item in rule["regions"]
                        if item.startswith("!")
                    }
                    and (
                        not any(
                            not item.startswith("!")
                            for item in rule["regions"]
                        )
                        or legacy_region in rule["regions"]
                    )
                )
            )

            checks.append(
                (
                    "Region",
                    region_matches,
                )
            )

        if "max_orbital_period" in rule:
            orbital_period = planet.get("orbital_period")
            checks.append(
                (
                    "Maximum Orbital Period",
                    orbital_period is not None
                    and orbital_period < rule["max_orbital_period"],
                )
            )

        if "distance" in rule:
            distance = planet.get("distance_from_arrival")
            checks.append(
                (
                    "Distance From Arrival",
                    distance is not None and distance >= rule["distance"],
                )
            )

        if "star" in rule:
            checks.append(
                (
                    "System Star",
                    self._stars_match(
                        planet.get("stars", []),
                        rule["star"],
                    ),
                )
            )

        if "parent_star" in rule:
            checks.append(
                (
                    "Parent Star",
                    self._stars_match(
                        planet.get("stars", []),
                        rule["parent_star"],
                    ),
                )
            )

        if "region" in rule:
            region_id = planet.get("region_id")
            requested = rule["region"]
            requested = (
                requested if isinstance(requested, list) else [requested]
            )
            checks.append(
                (
                    "Special Region",
                    region_id is not None
                    and any(
                        region_id in REGION_GROUPS.get(group, [])
                        for group in requested
                    ),
                )
            )

        if "guardian" in rule:
            position = planet.get("system_position")
            in_guardian_zone = bool(
                position
                and any(
                    system_distance(position, coordinates) < max_distance
                    for max_distance, coordinates in GUARDIAN_ZONES.values()
                )
            )
            checks.append(
                (
                    "Guardian Zone",
                    in_guardian_zone if rule["guardian"] else True,
                )
            )

        if "tuber" in rule:
            position = planet.get("system_position")
            requested = rule["tuber"]
            requested = (
                requested if isinstance(requested, list) else [requested]
            )
            in_tuber_zone = bool(
                position
                and any(
                    ("Any" in requested or name in requested)
                    and minimum <= system_distance(position, coordinates)
                    <= maximum
                    for name, (
                        (minimum, maximum),
                        coordinates,
                    ) in TUBER_ZONES.items()
                )
            )
            checks.append(("Tuber Zone", in_tuber_zone))

        if "bodies" in rule:
            body_types = set(planet.get("body_types", []))
            checks.append(
                (
                    "System Bodies",
                    any(
                        required in body_types
                        for required in rule["bodies"]
                    ),
                )
            )

        if "nebula" in rule:
            checks.append(
                (
                    "Nebula Proximity",
                    is_near_nebula(
                        str(planet.get("system_name", "")),
                        planet.get("system_position"),
                        str(rule["nebula"]),
                    ),
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

    @classmethod
    def _stars_match(cls, stars: list[dict], expected: Any) -> bool:
        expectations = expected if isinstance(expected, list) else [expected]

        for expectation in expectations:
            if isinstance(expectation, list):
                expected_type = expectation[0]
                expected_luminosity = expectation[1]
            else:
                expected_type = expectation
                expected_luminosity = None

            for star in stars:
                if not cls._star_type_matches(
                    str(expected_type),
                    str(star.get("type", "")),
                ):
                    continue

                if expected_luminosity is None:
                    return True

                luminosity = str(star.get("luminosity", ""))
                if luminosity.startswith(str(expected_luminosity)):
                    return True

        return False

    @staticmethod
    def _star_type_matches(expected: str, actual: str) -> bool:
        families = {
            "A": {"A", "A_BlueWhiteSuperGiant"},
            "B": {"B", "B_BlueWhiteSuperGiant"},
            "F": {"F", "F_WhiteSuperGiant"},
            "G": {"G", "G_WhiteSuperGiant"},
            "K": {"K", "K_OrangeGiant"},
            "M": {"M", "M_RedGiant", "M_RedSuperGiant"},
        }
        if expected in {"D", "C", "W"}:
            return actual.startswith(expected)
        return actual in families.get(expected, {expected})
