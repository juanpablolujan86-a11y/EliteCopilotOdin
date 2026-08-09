from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import tempfile
import unittest

from freyja.route_tracker import ActiveTradeRoute


class ActiveTradeRouteTests(unittest.TestCase):
    def trade(self, commodity, buy, sell):
        return SimpleNamespace(
            units=24,
            opportunity=SimpleNamespace(
                commodity=commodity, buy_system=buy, buy_station=f"{buy} Port",
                sell_system=sell, sell_station=f"{sell} Port",
            ),
        )

    def test_persists_advances_and_completes_from_confirmed_sales(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"active.json"
            bus=Mock()
            copied=[]
            tracker=ActiveTradeRoute(path,bus,copied.append)
            tracker.activate(SimpleNamespace(legs=(
                self.trade("silver","A","B"),self.trade("gold","B","C"),
            )))
            self.assertEqual(copied,["A"])
            restored=ActiveTradeRoute(path,bus,copied.append)
            self.assertEqual(restored.state["index"],0)

            restored.handle_market_buy({"Type":"silver"})
            self.assertEqual(copied[-1],"B")
            self.assertIn(
                "Compra confirmada",bus.publish_internal.call_args.args[1].message
            )
            restored.handle_market_sell({"Type":"silver"})
            self.assertEqual(restored.state["index"],1)
            self.assertEqual(copied[-1],"B")
            message=bus.publish_internal.call_args.args[1].message
            self.assertIn("Siguiente tramo",message)
            self.assertIn("24 toneladas de gold",message)

            restored.handle_market_sell({"Type":"gold"})
            self.assertIsNone(restored.state)
            self.assertFalse(path.exists())
            self.assertIn(
                "Ruta comercial completada",
                bus.publish_internal.call_args.args[1].message,
            )

    def test_ignores_sale_from_another_commodity(self):
        with tempfile.TemporaryDirectory() as directory:
            bus=Mock()
            tracker=ActiveTradeRoute(Path(directory)/"active.json",bus,Mock())
            tracker.activate(self.trade("silver","A","B"))
            tracker.handle_market_sell({"Type":"gold"})
            self.assertEqual(tracker.state["index"],0)
            bus.publish_internal.assert_not_called()


if __name__=="__main__":
    unittest.main()
