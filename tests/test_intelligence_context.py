import unittest

from heimdall.navigation import NavigationContext, RouteWaypoint
from intelligence.context import build_live_context
from intelligence.assistant import odin_system_prompt
from models.events.expedition_balance_updated import ExpeditionBalanceUpdated
from state.commander_state import CommanderState


class IntelligenceContextTests(unittest.TestCase):
    def test_prompt_and_scientific_context_follow_selected_language(self) -> None:
        commander = CommanderState(
            commander_name="Alex", current_system="Sol",
            last_scanned_body="Sol A 1", biology_signal_count=1,
        )

        english = build_live_context(
            commander, None, None,
            {"Sol A 1": ("Bacterium Aurasus",)}, language="en-US",
        )
        portuguese = build_live_context(
            commander, None, None,
            {"Sol A 1": ("Bacterium Aurasus",)}, language="pt-BR",
        )

        self.assertIn("Current system: Sol", english)
        self.assertIn("planet A 1: Bacterium Aurasus", english)
        self.assertIn("System exploration", english)
        self.assertIn("Sistema atual: Sol", portuguese)
        self.assertIn("sinais biológicos", portuguese)
        self.assertIn("Reply clearly and briefly in English", odin_system_prompt("en-GB"))
        self.assertIn("Responda em português", odin_system_prompt("pt-BR"))

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

        context = build_live_context(
            commander,
            navigation,
            balance,
            {"Sol A 1": ("Bacterium Aurasus", "Stratum Tectonicas")},
            "GCRV 1568",
        )

        self.assertIn("Sistema actual: Sol", context)
        self.assertIn("Cuerpo actual: planeta A 1", context)
        self.assertIn("0 saltos realizados y 1 restantes", context)
        self.assertIn("potencial con bonificaciones: 10000 créditos", context)
        self.assertIn(
            "planeta A 1: Bacterium Aurasus, Stratum Tectonicas", context
        )
        biology_section = context.split(
            "Biologías probables conocidas en el sistema, sin precios:"
        )[1]
        self.assertNotIn("Sol A 1", biology_section)
        self.assertIn("Base del comandante: GCRV 1568", context)
        self.assertNotIn("1000", biology_section)


if __name__ == "__main__":
    unittest.main()
