from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import tempfile, unittest
from freyja.planner import MarketOpportunity, QuickRouteOptimizer, TradeProfileBuilder

class FreyjaPlannerTests(unittest.TestCase):
    def test_profile_protects_rebuy_and_reads_cargo(self):
        with tempfile.TemporaryDirectory() as directory:
            cargo=Path(directory)/"Cargo.json"
            cargo.write_text('{"Vessel":"Ship","Count":24}',encoding="utf-8")
            profile=TradeProfileBuilder.build(
                SimpleNamespace(credits=1_000_000,current_system="Sol"),
                SimpleNamespace(current_system="Sol",rebuy_cost=100_000,
                                cargo_capacity=100,max_jump_range=30),cargo)
            self.assertEqual((profile.cargo_free,profile.reserve_credits,
                              profile.available_capital),(76,200_000,800_000))

    def test_profile_detects_large_ship_pad_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            profile=TradeProfileBuilder.build(
                SimpleNamespace(credits=1_000_000,current_system="Sol"),
                SimpleNamespace(current_system="Sol",rebuy_cost=100_000,
                                cargo_capacity=700,max_jump_range=25,
                                ship_type="Type9_Heavy"),
                Path(directory)/"Cargo.json",
            )
            self.assertTrue(profile.requires_large_pad)

    def test_profile_detects_panther_clipper_mk_ii_as_large_ship(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = TradeProfileBuilder.build(
                SimpleNamespace(credits=1_000_000, current_system="Sol"),
                SimpleNamespace(
                    current_system="Sol", rebuy_cost=100_000,
                    cargo_capacity=1044, max_jump_range=32,
                    ship_type="panthermkii",
                ),
                Path(directory) / "Cargo.json",
            )

            self.assertTrue(profile.requires_large_pad)

    def test_panther_rejects_powerplay_route_without_large_buy_pad(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = TradeProfileBuilder.build(
                SimpleNamespace(credits=100_000_000, current_system="Sol"),
                SimpleNamespace(
                    current_system="Sol", rebuy_cost=100_000,
                    cargo_capacity=1044, max_jump_range=32,
                    ship_type="panthermkii",
                ),
                Path(directory) / "Cargo.json",
            )
        opportunity = MarketOpportunity(
            "silver", "A", "Puesto mediano", "B", "Puerto grande",
            1_000, 2_000, 2_000, 2_000, 1, 500,
            datetime.now(timezone.utc).isoformat(),
            buy_has_large_pad=False, sell_has_large_pad=True,
        )

        self.assertIsNone(QuickRouteOptimizer().choose(profile, [opportunity]))

    def test_quick_route_prefers_profit_per_minute_and_respects_demand(self):
        now=datetime.now(timezone.utc).isoformat()
        profile=SimpleNamespace(cargo_free=100,available_capital=1_000_000)
        slow=MarketOpportunity("oro","A","Uno","B","Dos",1000,3000,100,100,8,100000,now)
        quick=MarketOpportunity("plata","A","Uno","C","Tres",1000,3000,100,30,1,500,now)
        plan=QuickRouteOptimizer().choose(profile,[slow,quick])
        self.assertEqual(plan.opportunity.commodity,"plata")
        self.assertEqual(plan.units,9)
        self.assertEqual(plan.recommended_sale_tons,9)
        self.assertLessEqual(plan.estimated_bulk_discount,0.08)

if __name__=="__main__": unittest.main()
