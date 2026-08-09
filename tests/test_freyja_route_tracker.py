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

    def plan(self, *trades, profit=500000):
        return SimpleNamespace(legs=trades,estimated_profit=profit)

    def test_persists_advances_and_completes_from_confirmed_sales(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"active.json"
            bus=Mock()
            copied=[]
            tracker=ActiveTradeRoute(path,bus,copied.append)
            tracker.activate(self.plan(
                self.trade("silver","A","B"),self.trade("gold","B","C"),
                profit=606984,
            ))
            self.assertEqual(copied,["A"])
            restored=ActiveTradeRoute(path,bus,copied.append)
            self.assertEqual(restored.state["index"],0)
            self.assertIn("Tramo 1 de 2",restored.status_message())
            self.assertIn("compre 24 toneladas de silver",restored.status_message())
            self.assertIn("606984 créditos",restored.status_message())

            restored.handle_fsd_jump({"StarSystem":"A"})
            self.assertIn("Llegamos al sistema de compra",bus.publish_internal.call_args.args[1].message)
            calls=bus.publish_internal.call_count
            restored.handle_fsd_jump({"StarSystem":"A"})
            self.assertEqual(bus.publish_internal.call_count,calls)
            restored.handle_docked({"StationName":"A Port"})
            self.assertIn("Atraque confirmado",bus.publish_internal.call_args.args[1].message)
            self.assertIn("Compre 24 toneladas",bus.publish_internal.call_args.args[1].message)
            restored.handle_market_buy({"Type":"silver"})
            self.assertEqual(copied[-1],"B")
            self.assertIn("venda 24 toneladas de silver",restored.status_message())
            self.assertIn("No recalcularé",restored.recalculation_blocker())
            self.assertIn("Advertencia:",restored.cancellation_warning())
            self.assertIn("dejará de guiar",restored.cancellation_warning())
            self.assertIn(
                "Compra confirmada",bus.publish_internal.call_args.args[1].message
            )
            restored.handle_fsd_jump({"StarSystem":"B"})
            self.assertIn("Llegamos al sistema de venta",bus.publish_internal.call_args.args[1].message)
            self.assertIn("B Port",bus.publish_internal.call_args.args[1].message)
            restored.handle_docked({"StationName":"B Port"})
            self.assertIn("Venda 24 toneladas",bus.publish_internal.call_args.args[1].message)
            restored.handle_market_sell({"Type":"silver"})
            self.assertEqual(restored.state["index"],1)
            self.assertEqual(copied[-1],"B")
            message=bus.publish_internal.call_args.args[1].message
            self.assertIn("Siguiente tramo",message)
            self.assertIn("24 toneladas de gold",message)

            restored.handle_market_buy({"Type":"gold","Count":24})
            restored.handle_market_sell({"Type":"gold"})
            self.assertIsNone(restored.state)
            self.assertFalse(path.exists())
            self.assertIn("No hay una ruta comercial activa",restored.status_message())
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

    def test_partial_sale_survives_restart_and_advances_only_when_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"active.json"
            bus=Mock()
            tracker=ActiveTradeRoute(path,bus,Mock())
            tracker.activate(self.trade("silver","A","B"))
            tracker.handle_market_buy({"Type":"silver","Count":24})
            tracker.handle_market_sell({"Type":"silver","Count":10})
            self.assertEqual(tracker.state["index"],0)
            self.assertIn("venda 14 toneladas",tracker.status_message())

            restored=ActiveTradeRoute(path,bus,Mock())
            self.assertIn("venda 14 toneladas",restored.status_message())
            restored.handle_market_sell({"Type":"silver","Count":14})
            self.assertIsNone(restored.state)
            self.assertIn(
                "Ruta comercial completada",
                bus.publish_internal.call_args.args[1].message,
            )

    def test_cancel_removes_persisted_route(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"active.json"
            tracker=ActiveTradeRoute(path,Mock(),Mock())
            self.assertFalse(tracker.cancel())

    def test_atomic_save_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"active.json"
            tracker=ActiveTradeRoute(path,Mock(),Mock())

            tracker.activate(self.trade("silver","A","B"))

            self.assertTrue(path.exists())
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_corrupt_state_is_ignored_and_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"active.json"
            path.write_text("{estado incompleto",encoding="utf-8")
            diagnostics=Mock()

            tracker=ActiveTradeRoute(path,Mock(),Mock(),diagnostics)

            self.assertIsNone(tracker.state)
            diagnostics.record_route_event.assert_called_once()
            self.assertEqual(
                diagnostics.record_route_event.call_args.args[0],
                "recuperacion_fallida",
            )

    def test_strategy_is_persisted_for_recalculation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"active.json"
            tracker=ActiveTradeRoute(path,Mock(),Mock())
            self.assertIsNone(tracker.active_strategy())
            tracker.activate(self.trade("silver","A","B"),"expedition")
            restored=ActiveTradeRoute(path,Mock(),Mock())
            self.assertEqual(restored.active_strategy(),"expedition")
            tracker.activate(self.trade("silver","A","B"))
            self.assertTrue(path.exists())
            self.assertTrue(tracker.cancel())
            self.assertFalse(path.exists())
            self.assertIsNone(tracker.state)
            self.assertFalse(tracker.cancel())

    def test_records_route_lifecycle_without_changing_voice_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            diagnostics=Mock()
            tracker=ActiveTradeRoute(
                Path(directory)/"active.json", Mock(), Mock(), diagnostics
            )
            tracker.activate(self.trade("silver","A","B"),"quick")
            tracker.handle_fsd_jump({"StarSystem":"A"})
            tracker.handle_docked({"StationName":"A Port"})
            tracker.handle_market_buy({"Type":"silver","Count":24})
            tracker.handle_market_sell({"Type":"silver","Count":10})
            tracker.handle_market_sell({"Type":"silver","Count":14})

            actions = [call.args[0] for call in diagnostics.record_route_event.call_args_list]
            self.assertEqual(
                actions,
                ["activada","llegada","atraque","compra","venta_parcial","completada"],
            )


if __name__=="__main__":
    unittest.main()
