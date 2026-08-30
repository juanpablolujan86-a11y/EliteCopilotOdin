"""Cálculo auditable del rendimiento de una operación minera."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MiningPerformance:
    duration_hours: float = 0.0
    produced_tonnes: int = 0
    tonnes_per_hour: float = 0.0
    estimated_value: int = 0
    estimated_credits_per_hour: float = 0.0
    realized_revenue: int = 0
    realized_credits_per_hour: float = 0.0

    def to_dict(self) -> dict:
        return {
            "duration_hours": self.duration_hours,
            "produced_tonnes": self.produced_tonnes,
            "tonnes_per_hour": self.tonnes_per_hour,
            "estimated_value": self.estimated_value,
            "estimated_credits_per_hour": self.estimated_credits_per_hour,
            "realized_revenue": self.realized_revenue,
            "realized_credits_per_hour": self.realized_credits_per_hour,
        }


def calculate_mining_performance(session, duration_hours: float) -> MiningPerformance:
    """Separa valor potencial de ingresos confirmados por el Journal."""

    hours = max(0.0, float(duration_hours or 0.0))
    produced = sum(max(0, int(value or 0)) for value in session.produced.values())
    revenue = max(0, int(session.sale_revenue or 0))
    valuation = session.valuation if isinstance(session.valuation, dict) else {}
    destination = valuation.get("best_permanent", {}) or {}
    unit_price = max(0, int(destination.get("unit_price", 0) or 0))
    estimated_value = produced * unit_price if unit_price else 0
    return MiningPerformance(
        duration_hours=hours,
        produced_tonnes=produced,
        tonnes_per_hour=(produced / hours if hours else 0.0),
        estimated_value=estimated_value,
        estimated_credits_per_hour=(estimated_value / hours if hours else 0.0),
        realized_revenue=revenue,
        realized_credits_per_hour=(revenue / hours if hours else 0.0),
    )
