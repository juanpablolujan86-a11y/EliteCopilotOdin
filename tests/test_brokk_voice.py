import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from brokk.session import MiningSession
from core.command_center import CommandCenter
from models.events.voice_message_ready import VoiceMessageReady


class BrokkVoiceTests(unittest.TestCase):
    def test_extracts_mineral_from_voice_request(self):
        self.assertEqual(
            CommandCenter._brokk_mining_request("BROKK, quiero minar platino"),
            "platino",
        )
        self.assertEqual(
            CommandCenter._brokk_mining_request("Vamos a minar painita, por favor"),
            "painita",
        )

    def test_does_not_confuse_generic_mining_question_with_search(self):
        self.assertIsNone(
            CommandCenter._brokk_mining_request("¿Cuál es mi estado de minería?")
        )
        self.assertTrue(
            CommandCenter._is_brokk_status_request("¿Cuál es mi estado de minería?")
        )

    def test_summary_reports_production_and_remaining_mined_cargo(self):
        center = CommandCenter.__new__(CommandCenter)
        session = MiningSession(
            active=True,
            status="extracting",
            started_at="2026-08-16T00:00:00+00:00",
            target_mineral="Platino",
            produced={"Platinum": 12},
            refined={"Platinum": 9},
        )
        center.brokk_processor = SimpleNamespace(session=session)
        center._mining_duration_hours = lambda _session: 2.0

        answer = center._brokk_voice_summary()

        self.assertIn("12 toneladas", answer)
        self.assertIn("6 toneladas por hora", answer)
        self.assertIn("Quedan 9 toneladas", answer)

    def test_announces_fill_thresholds_only_once(self):
        center = CommandCenter.__new__(CommandCenter)
        session = MiningSession(
            active=True,
            status="extracting",
            started_at="2026-08-16T00:00:00+00:00",
            cargo_count=92,
            equipment={"cargo_capacity": 100},
        )
        store = Mock()
        center.brokk_processor = SimpleNamespace(session=session, store=store)
        center.event_bus = Mock()

        center._announce_brokk_transition(
            event_name="Cargo", previous_active=True,
            previous_started_at=session.started_at,
        )
        center._announce_brokk_transition(
            event_name="Cargo", previous_active=True,
            previous_started_at=session.started_at,
        )

        self.assertEqual(session.announced_fill_levels, [75, 90])
        self.assertEqual(center.event_bus.publish_internal.call_count, 1)
        store.save.assert_called_once_with(session)

    def test_announces_first_tonne_and_completed_summary(self):
        center = CommandCenter.__new__(CommandCenter)
        session = MiningSession(
            active=True,
            status="extracting",
            started_at="2026-08-16T00:00:00+00:00",
            produced={"Platinum": 1},
            refined={"Platinum": 1},
        )
        center.brokk_processor = SimpleNamespace(session=session, store=Mock())
        center.event_bus = Mock()
        center._mining_duration_hours = lambda _session: 1.0

        center._announce_brokk_transition(
            event_name="MiningRefined", previous_active=False,
            previous_started_at="",
        )
        session.active = False
        session.status = "completed"
        center._announce_brokk_transition(
            event_name="SupercruiseEntry", previous_active=True,
            previous_started_at=session.started_at,
        )

        messages = [
            call.args[1].message
            for call in center.event_bus.publish_internal.call_args_list
            if isinstance(call.args[1], VoiceMessageReady)
        ]
        self.assertIn("primera tonelada de Platinum", messages[0])
        self.assertIn("Operación minera finalizada", messages[1])

        manifest = next(
            call.args[1]
            for call in center.event_bus.publish_internal.call_args_list
            if isinstance(call.args[1], dict)
        )
        self.assertEqual(manifest["cargo"], {"Platinum": 1})
        self.assertEqual(manifest["source"], "BROKK")

    def test_freyja_handoff_keeps_manifest_local_until_requested(self):
        center = CommandCenter.__new__(CommandCenter)
        center._mining_sale_manifest = {}

        center._handle_mining_cargo_ready({
            "system": "Sol",
            "body": "Sol A Belt",
            "cargo": {"Platinum": 20},
            "produced": {"Platinum": 24},
            "transferred_to_carrier": {"Platinum": 4},
        })

        self.assertEqual(
            center._mining_sale_manifest["cargo"], {"Platinum": 20}
        )
        self.assertEqual(
            center._mining_sale_manifest["status"],
            "Esperando orden para buscar venta",
        )

    def test_sale_search_requires_explicit_request(self):
        center = CommandCenter.__new__(CommandCenter)
        center._maybe_refresh_mining_valuation = Mock(return_value=True)

        self.assertTrue(center.request_mining_sale_search())

        center._maybe_refresh_mining_valuation.assert_called_once_with(force=True)

    def test_recognizes_explicit_voice_sale_request(self):
        self.assertTrue(CommandCenter._is_brokk_sale_request(
            "ODIN, ¿dónde vendo mi carga minera?"
        ))
        self.assertTrue(CommandCenter._is_brokk_sale_request(
            "BROKK, busca el mejor destino para vender los minerales"
        ))
        self.assertFalse(CommandCenter._is_brokk_sale_request(
            "¿Cuánta carga minera tengo?"
        ))


if __name__ == "__main__":
    unittest.main()
