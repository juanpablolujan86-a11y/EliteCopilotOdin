import unittest

from heimdall.navigation import NavigationContext, RouteWaypoint
from intelligence.context import build_live_context
from models.events.expedition_balance_updated import ExpeditionBalanceUpdated
from state.commander_state import CommanderState


class IntelligenceContextTests(unittest.TestCase):
    def test_live_context_contains_only_current_known_values(self) -> None:
        commander = CommanderState(
            commander_name="Juan",
            current_system="Sol",
            last_scanned_body="Sol A 1",
            expected_body_count=8,
            discovered_body_count=5,
            biology_signal_count=2,
        )
        navigation = NavigationContext(
            ship_name="Yggdrasil",
            fuel_main=20,
            fuel_capacity=32,
            current_system="Sol",
            target_system="Sirius",
            route=(
                RouteWaypoint("Sol", 1, (0, 0, 0), "G"),
                RouteWaypoint("Sirius", 2, (8, 0, 0), "A"),
            ),
        )
        balance = ExpeditionBalanceUpdated(1, 2, 0, 0, 1000, 2000, 10000, 0, 0)

        context = build_live_context(commander, navigation, balance)

        self.assertIn("Sistema actual: Sol", context)
        self.assertIn("Cuerpo actual: Sol A 1", context)
        self.assertIn("0 saltos realizados y 1 restantes", context)
        self.assertIn("Exobiología potencial: 10000 créditos", context)


if __name__ == "__main__":
    unittest.main()
