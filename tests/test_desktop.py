import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from core.command_center import CommandCenter
from core.processors.commander_state_updater import CommanderStateUpdater
from state.commander_state import CommanderState
from ui.desktop import GuiLogStream, OdinDesktopApp


class DesktopTests(unittest.TestCase):
    def test_fsd_jump_clears_previous_planet_context(self) -> None:
        state = CommanderState(current_body="Sistema anterior 4 a")

        CommanderStateUpdater(state).handle_fsd_jump({
            "StarSystem": "Sistema nuevo", "SystemAddress": 84,
        })

        self.assertEqual(state.current_body, "")

    def test_leaving_body_clears_context_without_touching_restored_system(self) -> None:
        state = CommanderState(current_body="Sistema 4 a")
        updater = CommanderStateUpdater(state)
        updater.restore_context({
            "StarSystem": "Sistema", "SystemAddress": 42,
            "StarPos": [1.0, 2.0, 3.0], "StarClass": "K",
            "timestamp": "2026-08-10T00:00:00Z",
        })

        updater.handle_leave_body({"event": "LeaveBody"})

        self.assertEqual(state.current_body, "")
        self.assertEqual(state.star_position, (1.0, 2.0, 3.0))
        self.assertEqual(state.system_stars, [{"type": "K", "luminosity": ""}])

    def test_log_stream_queues_complete_text_without_blocking(self) -> None:
        messages = queue.Queue()
        stream = GuiLogStream(messages)

        text = "HEIMDALL: ruta calculada\n"
        written = stream.write(text)

        self.assertEqual(written, len(text))
        self.assertEqual(messages.get_nowait(), text)

    def test_credit_format_matches_spanish_dashboard(self) -> None:
        self.assertEqual(OdinDesktopApp._credits(359520), "359.520 CR")
        self.assertEqual(OdinDesktopApp._credits(97300000, True), "≈ 97.300.000 CR")

    def test_gui_neutron_route_request_is_normalized_and_queued_once(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center._manual_route_requests = queue.Queue()
        center._route_calculation_busy = threading.Event()

        self.assertTrue(center.request_neutron_route("  Colonia   Dream  "))
        self.assertEqual(center._manual_route_requests.get_nowait(), "Colonia Dream")
        center._manual_route_requests.put("pending")
        self.assertFalse(center.request_neutron_route("Sol"))

    def test_mimir_dashboard_includes_real_signal_planets_without_predictions(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center.commander_state = SimpleNamespace(system_address=42)
        center.database = Mock()
        center.database.query.side_effect = (
            [{
                "body_id": 5, "body_name": "Prueba 4 a",
                "source_event": "FSSBodySignals", "signal_type": "Biological",
                "signal_count": 2, "genus": None, "species": None,
            }],
            [{"body_id": 5, "body_name": "Prueba 4 a"}],
        )

        biology = center._dashboard_biology({})

        self.assertEqual(biology["bodies"], 1)
        self.assertEqual(biology["species"], 2)
        self.assertEqual(biology["details"][0]["body"], "Prueba 4 a")
        self.assertEqual(biology["details"][0]["signals"], 2)

    def test_mimir_dashboard_includes_approximate_probable_species_values(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center.commander_state = SimpleNamespace(system_address=None)
        center.database = Mock()

        biology = center._dashboard_biology(
            {"Prueba 4 a": ("Bacterium Informem",)},
            {"Prueba 4 a": {"Bacterium Informem": 8_418_000}},
        )

        self.assertEqual(
            biology["details"][0]["probable_values"],
            {"Bacterium Informem": 8_418_000},
        )

    def test_mimir_dashboard_tracks_organic_sample_progress(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center.commander_state = SimpleNamespace(system_address=42)
        center.surface_navigation = SimpleNamespace(
            species="Bacterium Informem", distance_m=75,
            required_distance_m=100, ready_for_sample=False,
        )
        center.database = Mock()
        center.database.query.side_effect = (
            [{
                "body_id": 5, "body_name": None,
                "source_event": "ScanOrganic", "signal_type": None,
                "signal_count": 1, "genus": "Bacterium",
                "species": "Bacterium Informem", "scan_type": "Log",
            }],
            [{"body_id": 5, "body_name": "Prueba 4 a"}],
        )

        biology = center._dashboard_biology({})
        sample = biology["details"][0]["sampling"][0]

        self.assertEqual(sample["progress"], 1)
        self.assertEqual(sample["distance_m"], 75)
        self.assertEqual(sample["required_distance_m"], 100)

    def test_mimir_dashboard_stays_empty_until_new_system_biology_arrives(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center.commander_state = SimpleNamespace(system_address=42, current_body="")
        center._mimir_visible_body_ids = set()
        center.database = Mock()
        center.database.query.side_effect = (
            [{
                "body_id": 5, "body_name": "Sistema 5",
                "source_event": "SAASignalsFound", "signal_type": "Biological",
                "signal_count": 1, "genus": "Bacteria", "species": None,
                "scan_type": None,
            }],
            [{"body_id": 5, "body_name": "Sistema 5"}],
        )

        biology = center._dashboard_biology({"Sistema 5": ("Bacterium Informem",)})

        self.assertEqual(biology["details"], ())

    def test_mimir_dashboard_shows_only_current_planet_and_dss_genus(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center.commander_state = SimpleNamespace(
            system_address=42, current_body="Sistema 2",
        )
        center._mimir_visible_body_ids = {1, 2}
        center.surface_navigation = SimpleNamespace(
            species="", distance_m=None, required_distance_m=None,
            ready_for_sample=False,
        )
        center.database = Mock()
        center.database.query.side_effect = (
            [
                {
                    "body_id": 1, "body_name": "Sistema 1",
                    "source_event": "FSSBodySignals", "signal_type": "Biological",
                    "signal_count": 1, "genus": None, "species": None,
                    "scan_type": None,
                },
                {
                    "body_id": 2, "body_name": "Sistema 2",
                    "source_event": "SAASignalsFound", "signal_type": "Biological",
                    "signal_count": 1, "genus": "Bacteria", "species": None,
                    "scan_type": None,
                },
            ],
            [
                {"body_id": 1, "body_name": "Sistema 1"},
                {"body_id": 2, "body_name": "Sistema 2"},
            ],
        )

        biology = center._dashboard_biology({
            "Sistema 1": ("Stratum Tectonicas",),
            "Sistema 2": ("Bacterium Informem",),
        })

        self.assertEqual(len(biology["details"]), 1)
        self.assertEqual(biology["details"][0]["body"], "Sistema 2")
        self.assertEqual(biology["details"][0]["confirmed"], ("Bacteria",))
        self.assertEqual(biology["details"][0]["probable"], ())
        self.assertEqual(biology["details"][0]["confirmation"], "DSS")

    def test_mimir_biology_is_rendered_as_vertical_planet_list(self) -> None:
        text = OdinDesktopApp._biology_details_text({"details": ({
            "body": "Prueba 4 a", "signals": 2, "confirmed": (),
            "probable": ("Bacterium Informem", "Stratum Tectonicas"),
            "probable_values": {
                "Bacterium Informem": 8_418_000,
                "Stratum Tectonicas": 19_010_800,
            },
            "probable_rewards": {
                "Bacterium Informem": {
                    "base": 8_418_000, "potential": 42_090_000,
                },
                "Stratum Tectonicas": {
                    "base": 19_010_800, "potential": 19_010_800,
                },
            },
        },)})

        self.assertEqual(text.splitlines(), [
            "◆ Prueba 4 a · 2 señales",
            "  ◇ Bacterium Informem — PRIMERA PISADA ×5: ≈ 42.090.000 CR",
            "  ◇ Stratum Tectonicas — NORMAL: ≈ 19.010.800 CR",
        ])

    def test_mimir_sample_tracking_shows_progress_distance_and_completion(self) -> None:
        text = OdinDesktopApp._sampling_details_text({"details": ({
            "body": "Prueba 4 a",
            "sampling": (
                {
                    "species": "Bacterium Informem", "progress": 1,
                    "distance_m": 63.5, "required_distance_m": 100,
                    "ready": False,
                },
                {
                    "species": "Stratum Tectonicas", "progress": 3,
                    "distance_m": None, "required_distance_m": None,
                    "ready": False,
                },
            ),
        },)})

        self.assertIn("Bacterium Informem · 1/3", text)
        self.assertIn("64/100 m · faltan 36 m", text)
        self.assertIn("Stratum Tectonicas · 3/3 COMPLETADA", text)

    def test_freyja_dashboard_exposes_active_trade_leg(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center.freyja_ledger = Mock()
        center.freyja_ledger.summary.return_value = SimpleNamespace(
            realized_profit=250000, cargo_units=64
        )
        center.active_trade_route = SimpleNamespace(state={
            "index": 0, "phase": "to_sell", "strategy": "quick",
            "estimated_profit": 900000,
            "bought_units": 64, "sold_units": 4,
            "legs": [{
                "commodity": "Oro", "units": 64,
                "buy_system": "Sol", "buy_station": "Galileo",
                "sell_system": "Achenar", "sell_station": "Dawes Hub",
            }],
        })

        trade = center._dashboard_trade()

        self.assertTrue(trade["active"])
        self.assertEqual(trade["strategy"], "Ruta rápida")
        self.assertEqual(trade["units"], 60)
        self.assertIn("Dawes Hub", trade["target"])
        self.assertEqual(trade["realized_profit"], 250000)

    def test_freyja_gui_accepts_only_one_valid_trade_request(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center._manual_trade_requests = queue.Queue()
        center._trade_calculation_busy = threading.Event()
        center._trade_requested_strategy = ""

        self.assertTrue(center.request_trade_calculation("three_station"))
        self.assertEqual(center._manual_trade_requests.get_nowait(), "three_station")
        self.assertEqual(center._trade_requested_strategy, "three_station")
        self.assertFalse(center.request_trade_calculation("invalid"))
        center._trade_calculation_busy.set()
        self.assertFalse(center.request_trade_calculation("quick"))


if __name__ == "__main__":
    unittest.main()
