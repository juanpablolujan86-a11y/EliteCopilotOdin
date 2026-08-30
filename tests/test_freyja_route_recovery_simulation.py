"""Simulacion aislada del ciclo comercial con reinicios de ODIN."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import tempfile
import unittest

from core.database import DatabaseManager
from freyja.ledger import TradeLedger
from freyja.route_tracker import ActiveTradeRoute


class FreyjaRouteRecoverySimulationTests(unittest.TestCase):
    @staticmethod
    def trade(commodity, buy_system, sell_system, units=24):
        return SimpleNamespace(
            units=units,
            opportunity=SimpleNamespace(
                commodity=commodity,
                buy_system=buy_system,
                buy_station=f"{buy_system} Port",
                sell_system=sell_system,
                sell_station=f"{sell_system} Port",
            ),
        )

    def test_three_leg_route_and_ledger_survive_repeated_restarts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            database=DatabaseManager(root/"database")
            database.connect()
            try:
                database.create_tables()
                ledger=TradeLedger(database)
                route_path=root/"freyja"/"active_route.json"
                diagnostics=Mock()
                bus=Mock()
                copied=[]
                plan=SimpleNamespace(
                    legs=(
                        self.trade("silver","A","B"),
                        self.trade("gold","B","C"),
                        self.trade("medicine","C","A"),
                    ),
                    estimated_profit=720000,
                )

                tracker=ActiveTradeRoute(route_path,bus,copied.append,diagnostics)
                tracker.activate(plan,"three_station")
                prices=(("silver",10000,18000),("gold",8000,14000),
                        ("medicine",4000,9000))
                for index,(commodity,buy_price,sell_price) in enumerate(prices):
                    tracker=ActiveTradeRoute(
                        route_path,bus,copied.append,diagnostics
                    )
                    self.assertEqual(tracker.state["index"],index)
                    tracker.handle_market_buy({"Type":commodity,"Count":24})
                    ledger.handle({
                        "timestamp":f"buy-{index}","event":"MarketBuy",
                        "Type":commodity,"Count":24,"BuyPrice":buy_price,
                    })

                    tracker=ActiveTradeRoute(
                        route_path,bus,copied.append,diagnostics
                    )
                    self.assertEqual(tracker.state["phase"],"to_sell")
                    tracker.handle_market_sell({"Type":commodity,"Count":12})
                    tracker=ActiveTradeRoute(
                        route_path,bus,copied.append,diagnostics
                    )
                    self.assertIn("venda 12 toneladas",tracker.status_message())
                    tracker.handle_market_sell({"Type":commodity,"Count":12})
                    ledger.handle({
                        "timestamp":f"sell-{index}","event":"MarketSell",
                        "Type":commodity,"Count":24,"SellPrice":sell_price,
                        "AvgPricePaid":buy_price,
                    })

                summary=ledger.summary()
                self.assertIsNone(tracker.state)
                self.assertFalse(route_path.exists())
                self.assertEqual(summary.purchases,72)
                self.assertEqual(summary.sales,72)
                self.assertEqual(summary.cargo_units,0)
                self.assertEqual(summary.realized_profit,456000)
                recovered=[
                    call for call in diagnostics.record_route_event.call_args_list
                    if call.args[0]=="recuperada"
                ]
                self.assertGreaterEqual(len(recovered),6)
            finally:
                database.disconnect()


if __name__=="__main__":
    unittest.main()
