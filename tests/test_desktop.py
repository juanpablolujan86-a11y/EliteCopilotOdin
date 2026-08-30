import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from core.command_center import CommandCenter
from core.processors.commander_state_updater import CommanderStateUpdater
from state.commander_state import CommanderState
from ui.desktop import GuiLogStream, OdinDesktopApp
from ui.voice_commands import voice_command_catalog


class DesktopTests(unittest.TestCase):
    def test_voice_command_catalog_contains_critical_officer_commands(self) -> None:
        spanish = dict(voice_command_catalog("es-419"))
        all_spanish = "\n".join(
            command for commands in spanish.values() for command in commands
        )
        self.assertIn("Solicita atraque", all_spanish)
        self.assertIn("Autorizo la inyección FSD", all_spanish)
        self.assertIn("Quiero comerciar", all_spanish)
        self.assertIn("Quiero minar [mineral]", all_spanish)

        english = dict(voice_command_catalog("en-GB"))
        portuguese = dict(voice_command_catalog("pt-BR"))
        self.assertTrue(any("Request docking" in item for items in english.values() for item in items))
        self.assertTrue(any("Solicite atracação" in item for items in portuguese.values() for item in items))

    def test_powerplay_weekly_guide_covers_all_supported_families(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        guide = dict(center.powerplay_weekly_guide())
        self.assertEqual(set(guide), {
            "megaship", "combat", "trade", "mining", "transport",
            "exploration", "on_foot", "salvage", "crime",
        })
        self.assertTrue(all(steps for steps in guide.values()))

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

    def test_brokk_prospect_is_rendered_as_vertical_material_list(self) -> None:
        text = OdinDesktopApp._mining_prospect_text({
            "content": "Contenido alto", "remaining": 82.5,
            "materials": (
                {"name": "Platino", "proportion": 42.5},
                {"name": "Osmio", "proportion": 18.0},
            ),
        })
        self.assertEqual(text.splitlines(), [
            "Contenido alto", "Reserva restante: 82.5%",
            "◆ Platino · 42.5%", "◆ Osmio · 18.0%",
        ])

    def test_brokk_inventory_is_sorted_by_quantity(self) -> None:
        text = OdinDesktopApp._mining_inventory_text(
            {"Platino": 3, "Osmio": 8}, "Vacío", "t"
        )
        self.assertEqual(text.splitlines(), ["◆ Osmio · 8 t", "◆ Platino · 3 t"])

    def test_brokk_equipment_lists_ready_and_missing_techniques(self) -> None:
        text = OdinDesktopApp._mining_equipment_text({
            "ship": "Type-10", "cargo_capacity": 256,
            "techniques": {
                "laser": {"ready": True, "missing": []},
                "abrasion": {"ready": True, "missing": []},
                "subsurface": {"ready": False, "missing": ["misiles subsuperficiales"]},
                "core": {"ready": False, "missing": ["cargas sísmicas"]},
            },
        })
        self.assertIn("✓ Láser de superficie · LISTA", text)
        self.assertIn("◇ Subsuperficie · falta: misiles subsuperficiales", text)

    def test_gui_neutron_route_request_is_normalized_and_queued_once(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center._manual_route_requests = queue.Queue()
        center._route_calculation_busy = threading.Event()

        self.assertTrue(center.request_neutron_route("  Colonia   Dream  "))
        self.assertEqual(center._manual_route_requests.get_nowait(), "Colonia Dream")
        center._manual_route_requests.put("pending")
        self.assertFalse(center.request_neutron_route("Sol"))

    def test_gui_exact_route_uses_current_cargo_and_rejects_missing_data(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center._manual_route_requests = queue.Queue()
        center._route_calculation_busy = threading.Event()
        center._manual_exact_route_requests = queue.Queue()
        center._exact_route_calculation_busy = threading.Event()
        center.trade_profile = SimpleNamespace(cargo_used=27)
        center.navigation_manager = SimpleNamespace(
            context=SimpleNamespace(
                exact_plotter_readiness=lambda: {"ready": True, "missing": ()}
            )
        )

        accepted, detail = center.request_exact_route("  Colonia   Dream ")

        self.assertTrue(accepted, detail)
        self.assertEqual(
            center._manual_exact_route_requests.get_nowait(),
            ("Colonia Dream", 27),
        )
        center.navigation_manager.context.exact_plotter_readiness = lambda: {
            "ready": False, "missing": ("masa sin carga",)
        }
        accepted, detail = center.request_exact_route("Sol")
        self.assertFalse(accepted)
        self.assertIn("masa sin carga", detail)

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
        app = OdinDesktopApp.__new__(OdinDesktopApp)
        app.odin = SimpleNamespace(config=SimpleNamespace(language="es-419"))
        text = app._biology_details_text({"details": ({
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
        app = OdinDesktopApp.__new__(OdinDesktopApp)
        app.odin = SimpleNamespace(config=SimpleNamespace(language="es-419"))
        text = app._sampling_details_text({"details": ({
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

    def test_freyja_dashboard_exposes_powerplay_sale_result(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center.freyja_ledger = Mock()
        center.freyja_ledger.summary.return_value = SimpleNamespace(
            realized_profit=0, cargo_units=12
        )
        center.active_trade_route = SimpleNamespace(state={
            "index": 0, "phase": "to_buy", "strategy": "quick",
            "legs": [{
                "commodity": "silver", "units": 3,
                "buy_system": "Piscium Sector DQ-Y b4",
                "buy_station": "Bobs Charcoal Grill",
            }],
        })
        center._powerplay_sale_result = {
            "active": True,
            "strategy": "Venta Powerplay",
            "commodity": "Reliquias de Soontill",
            "target": "Alfred Vincent Memorial Station · Trianguli Sector LS-T b3-1",
            "units": 12,
            "progress": "Destino de venta calculado (sin méritos confirmados)",
            "unit_price": 38818,
            "distance_ly": 180.1,
            "powerplay_state": "Exploited · Li Yong-Rui",
        }

        trade = center._dashboard_trade()

        self.assertTrue(trade["active"])
        self.assertEqual(trade["strategy"], "Venta Powerplay")
        self.assertEqual(trade["unit_price"], 38818)
        self.assertEqual(trade["distance_ly"], 180.1)
        self.assertIn("Alfred Vincent", trade["target"])
        self.assertIn("Li Yong-Rui", trade["powerplay_state"])

    def test_regular_trade_request_clears_powerplay_sale_result(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center._manual_trade_requests = queue.Queue()
        center._trade_calculation_busy = threading.Event()
        center._trade_requested_strategy = "powerplay"
        center._trade_requested_commodity = "Reliquias de Soontill"
        center._powerplay_sale_result = {"active": True}

        self.assertTrue(center.request_trade_calculation("quick", "silver"))

        self.assertEqual(center._powerplay_sale_result, {})

    def test_freyja_gui_accepts_only_one_valid_trade_request(self) -> None:
        center = CommandCenter.__new__(CommandCenter)
        center._manual_trade_requests = queue.Queue()
        center._trade_calculation_busy = threading.Event()
        center._trade_requested_strategy = ""
        center._trade_requested_commodity = ""

        self.assertTrue(center.request_trade_calculation("three_station", " Gold "))
        self.assertEqual(
            center._manual_trade_requests.get_nowait(),
            ("three_station", "gold", True),
        )
        self.assertEqual(center._trade_requested_strategy, "three_station")
        self.assertEqual(center._trade_requested_commodity, "gold")
        self.assertFalse(center.request_trade_calculation("invalid"))
        center._trade_calculation_busy.set()
        self.assertFalse(center.request_trade_calculation("quick"))

    def test_freyja_filters_market_options_by_requested_commodity(self) -> None:
        opportunities = [
            SimpleNamespace(commodity="gold"),
            SimpleNamespace(commodity="silver"),
            SimpleNamespace(commodity="golden algae"),
        ]

        filtered = CommandCenter._filter_trade_commodity(opportunities, " Gold ")

        self.assertEqual(
            [opportunity.commodity for opportunity in filtered],
            ["gold", "golden algae"],
        )
        self.assertIs(
            CommandCenter._filter_trade_commodity(opportunities, ""),
            opportunities,
        )


if __name__ == "__main__":
    unittest.main()
