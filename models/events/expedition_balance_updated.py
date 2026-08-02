"""Resumen monetario y de actividad de la expedición."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExpeditionBalanceUpdated:
    systems_visited: int
    bodies_scanned: int
    bodies_mapped: int
    species_completed: int
    cartography_estimated: int
    exobiology_base: int
    exobiology_potential: int
    exploration_sold: int
    exobiology_sold: int
    reason: str = ""

    @property
    def total_base(self) -> int:
        return self.cartography_estimated + self.exobiology_base

    @property
    def total_potential(self) -> int:
        return self.cartography_estimated + self.exobiology_potential

