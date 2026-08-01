"""Contexto de descubrimiento obtenido del Journal de Elite Dangerous."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DiscoveryContext:
    """Estado conocido de descubrimiento de un cuerpo planetario."""

    was_discovered: bool
    was_mapped: bool
    was_footfalled: bool
    landable: bool
    system_populated: bool = False

    @classmethod
    def from_scan_event(
        cls,
        event: dict[str, Any],
        system_population: int = 0,
    ) -> "DiscoveryContext":
        return cls(
            was_discovered=bool(event.get("WasDiscovered", False)),
            was_mapped=bool(event.get("WasMapped", False)),
            was_footfalled=bool(event.get("WasFootfalled", False)),
            landable=bool(event.get("Landable", False)),
            system_populated=system_population > 0,
        )

    @property
    def first_footfall_available(self) -> bool:
        return (
            self.landable
            and not self.was_footfalled
            and not self.system_populated
        )

    @property
    def first_logged_candidate(self) -> bool:
        """Señala una oportunidad, no una garantía de First Logged."""

        return self.first_footfall_available and not self.was_discovered

    def reasons(self) -> list[str]:
        reasons = [
            "Descubierto previamente: "
            + ("Sí" if self.was_discovered else "No"),
            "Cartografiado previamente: "
            + ("Sí" if self.was_mapped else "No"),
            "Primera pisada reclamada: "
            + ("Sí" if self.was_footfalled else "No"),
        ]

        if self.first_footfall_available:
            reasons.append("Primera pisada disponible según el Journal")

        if self.system_populated:
            reasons.append(
                "Sistema habitado: no se estima bonificación First Logged"
            )

        return reasons
