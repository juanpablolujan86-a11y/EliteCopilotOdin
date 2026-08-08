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

    def test_quick_route_prefers_profit_per_minute_and_respects_demand(self):
        now=datetime.now(timezone.utc).isoformat()
        profile=SimpleNamespace(cargo_free=100,available_capital=1_000_000)
        slow=MarketOpportunity("oro","A","Uno","B","Dos",1000,3000,100,100,8,100000,now)
        quick=MarketOpportunity("plata","A","Uno","C","Tres",1000,3000,100,30,1,500,now)
        plan=QuickRouteOptimizer().choose(profile,[slow,quick])
        self.assertEqual(plan.opportunity.commodity,"plata")
        self.assertEqual(plan.units,30)

if __name__=="__main__": unittest.main()
