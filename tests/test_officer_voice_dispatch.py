from dataclasses import replace
from datetime import datetime, timezone
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch
import queue
import threading
import unittest

from core.command_center import CommandCenter
from freyja.ledger import TradeSummary
from freyja.market_source import MarketSourceError
from freyja.planner import MarketOpportunity, TradeProfile
from models.events.voice_message_ready import VoiceMessageReady
from voice.service import VoiceServiceError

class OfficerVoiceDispatchTests(unittest.TestCase):
    def test_processing_messages_follow_selected_language(self):
        self.assertEqual(
            CommandCenter._processing_message_for("biology samples", "en-US"),
            "Checking the scientific records.",
        )
        self.assertEqual(
            CommandCenter._processing_message_for("dados do sistema", "pt-BR"),
            "Verificando o banco de dados.",
        )

    def test_wake_acknowledgements_follow_selected_language(self):
        center = CommandCenter.__new__(CommandCenter)
        center.config = SimpleNamespace(language="pt-BR")
        center._wake_acknowledgement_lock = threading.Lock()
        center._wake_acknowledgement_index = 0
        self.assertEqual(center._next_wake_acknowledgement(), "Sim, comandante?")

    def test_freyja_understands_powerplay_reinforcement_sale_request(self):
        self.assertEqual(
            CommandCenter._freyja_powerplay_sale_request(
                "Quiero vender Reliquias de Soontill en un sistema reinforcement de mi Powerplay"
            ),
            "reliquias de soontill",
        )
        self.assertIsNone(CommandCenter._freyja_powerplay_sale_request(
            "quiero vender oro"
        ))

    def test_disabling_wake_word_applies_immediately_and_clears_pending_audio(self):
        center = CommandCenter.__new__(CommandCenter)
        center.wake_listener = Mock()
        center.wake_listener.armed = threading.Event()
        center.wake_listener.armed.set()
        center._wake_activations = queue.Queue()
        center._voice_questions = queue.Queue()
        center._unclear_voice_commands = queue.Queue()
        center._wake_activations.put(True)
        center._voice_questions.put("estado")
        center._unclear_voice_commands.put(True)

        center.apply_voice_activation_mode(wake_enabled=False)

        center.wake_listener.enable_passive_listening.assert_called_once_with(False)
        self.assertFalse(center.wake_listener.armed.is_set())
        self.assertTrue(center._wake_activations.empty())
        self.assertTrue(center._voice_questions.empty())
        self.assertTrue(center._unclear_voice_commands.empty())

    def test_officer_message_is_logged_even_when_voice_is_muted(self):
        center = CommandCenter.__new__(CommandCenter)
        center.config = SimpleNamespace()
        center._voice_busy = threading.Event()
        center.wake_listener = Mock()
        message = VoiceMessageReady("MÍMIR", "Biología detectada.", "prueba")
        output = StringIO()

        with patch("core.command_center.OfficerVoiceService") as service:
            service.return_value.speak.side_effect = VoiceServiceError("silenciada")
            with redirect_stdout(output):
                center._run_officer_voice_message(message)

        self.assertIn("MÍMIR: Biología detectada.", output.getvalue())

    def test_heimdall_finishes_automatic_replan_on_main_loop(self):
        center = CommandCenter.__new__(CommandCenter)
        center._route_replan_busy = threading.Event()
        center._route_replan_busy.set()
        center.heimdall_route_planner = Mock()
        center.heimdall_diagnostics = Mock()
        center._officer_voice_messages = queue.Queue()
        plan = SimpleNamespace(
            destination_system="Destino",
            actual_total_jumps=12,
            next_waypoint=SimpleNamespace(system="Siguiente"),
        )

        center._finish_automatic_replan(plan, None, "Destino")

        center.heimdall_route_planner.activate.assert_called_once_with(plan)
        center.heimdall_diagnostics.record_planned_route.assert_called_once_with(plan)
        self.assertFalse(center._route_replan_busy.is_set())
        message = center._officer_voice_messages.get_nowait()
        self.assertEqual(message.officer, "HEIMDALL")
        self.assertIn("Ruta recalculada", message.message)
        self.assertIn("Siguiente", message.message)

    def test_heimdall_automatic_replan_failure_is_brief_and_nonblocking(self):
        center = CommandCenter.__new__(CommandCenter)
        center._route_replan_busy = threading.Event()
        center._route_replan_busy.set()
        center._officer_voice_messages = queue.Queue()

        center._finish_automatic_replan(None, "route_error", "Destino")

        self.assertFalse(center._route_replan_busy.is_set())
        message = center._officer_voice_messages.get_nowait()
        self.assertIn("no pude recalcular", message.message)
        self.assertNotIn("route_error", message.message)
    def test_heimdall_recognizes_fsd_injection_inventory_questions(self):
        self.assertTrue(CommandCenter._is_fsd_injection_status_request(
            "cuántas inyecciones FSD puedo fabricar"
        ))
        self.assertTrue(CommandCenter._is_fsd_injection_status_request(
            "tengo materiales para síntesis de salto"
        ))
        self.assertFalse(CommandCenter._is_fsd_injection_status_request(
            "cuánto combustible tengo"
        ))

    def test_heimdall_extracts_jump_distance_for_injection_advice(self):
        self.assertEqual(
            CommandCenter._fsd_injection_distance_request(
                "¿puedo saltar 95,5 años luz con una inyección?"
            ),
            95.5,
        )
        self.assertEqual(
            CommandCenter._fsd_injection_distance_request("alcanzar 120 ly"),
            120.0,
        )
        self.assertIsNone(CommandCenter._fsd_injection_distance_request(
            "tengo 120 toneladas de combustible"
        ))

    def test_heimdall_recognizes_route_injection_review(self):
        self.assertTrue(CommandCenter._is_route_injection_status_request(
            "¿necesito alguna inyección en esta ruta?"
        ))
        self.assertTrue(CommandCenter._is_route_injection_status_request(
            "revisá la síntesis necesaria para la ruta"
        ))
        self.assertFalse(CommandCenter._is_route_injection_status_request(
            "¿cuántos saltos quedan en la ruta?"
        ))

    def test_heimdall_requires_explicit_fsd_injection_authorization_phrase(self):
        self.assertTrue(CommandCenter._is_fsd_injection_authorization(
            "autorizo la inyección FSD"
        ))
        self.assertTrue(CommandCenter._is_fsd_injection_authorization(
            "confirmo esta inyección FSD"
        ))
        self.assertFalse(CommandCenter._is_fsd_injection_authorization(
            "quizás usemos una inyección FSD"
        ))

    def test_all_trade_modes_use_bubble_market_anchor_when_commander_is_far(self):
        center=CommandCenter.__new__(CommandCenter)
        center.trade_profile=TradeProfile(
            "Colonia",10_000_000,500_000,100,0,30,(10_000,0,0)
        )
        for selection in ("quick","three_station","expedition","powerplay"):
            planned=center._freyja_planning_profile(selection)
            self.assertEqual(planned.system,"Lembava")
            self.assertEqual(planned.position,center.BUBBLE_TRADE_CENTER)

    def test_freyja_allows_anticipatory_planning_with_full_cargo(self):
        profile=TradeProfile(
            "Wredgu MR-N d6-39",3_357_092_535,167_854_627,
            24,24,66.12,(-9491.0,-9.3,-451.2),
        )

        center=CommandCenter.__new__(CommandCenter)
        center.trade_profile=profile
        planned=center._freyja_planning_profile(
            "quick", replace(profile,cargo_used=0)
        )

        self.assertIsNone(CommandCenter._freyja_trade_profile_blocker(profile))
        self.assertEqual(planned.cargo_used,0)
        self.assertEqual(planned.cargo_free,24)

    def test_freyja_accepts_current_ship_when_cargo_is_free(self):
        profile=TradeProfile(
            "Lembava",3_357_092_535,167_854_627,
            24,0,66.12,CommandCenter.BUBBLE_TRADE_CENTER,
        )

        self.assertIsNone(CommandCenter._freyja_trade_profile_blocker(profile))

    def test_freyja_uses_cached_market_when_refresh_fails(self):
        center=CommandCenter.__new__(CommandCenter)
        center._freyja_used_stale_cache=False
        profile=TradeProfile(
            "Lembava",10_000_000,500_000,24,0,30,
            CommandCenter.BUBBLE_TRADE_CENTER,
        )
        cached=MarketOpportunity(
            "silver","A","Compra","B","Venta",10_000,20_000,
            100,100,1,100,datetime.now(timezone.utc).isoformat(),
        )
        cache=Mock()
        cache.refresh_region.side_effect=MarketSourceError("sin red")
        cache.opportunities.return_value=[cached]

        plan=center._refresh_and_recalculate_freyja("quick",profile,cache)

        self.assertIsNotNone(plan)
        self.assertTrue(center._freyja_used_stale_cache)
        self.assertEqual(plan.opportunity.commodity,"silver")

    def test_freyja_refreshes_external_markets_before_reading_cache(self):
        center=CommandCenter.__new__(CommandCenter)
        center._freyja_used_stale_cache=False
        profile=TradeProfile(
            "Lembava",10_000_000,500_000,24,0,30,
            CommandCenter.BUBBLE_TRADE_CENTER,
        )
        current=MarketOpportunity(
            "gold","A","Compra","B","Venta",10_000,20_000,
            100,100,1,100,datetime.now(timezone.utc).isoformat(),
        )
        cache=Mock()
        cache.opportunities.return_value=[current]

        plan=center._refresh_and_recalculate_freyja("quick",profile,cache)

        self.assertIsNotNone(plan)
        self.assertFalse(center._freyja_used_stale_cache)
        self.assertEqual(
            [call[0] for call in cache.method_calls[:2]],
            ["refresh_region", "opportunities"],
        )

    def test_new_trade_mode_cannot_replace_cargo_pending_for_sale(self):
        center=CommandCenter.__new__(CommandCenter)
        center.active_trade_route=Mock()
        center.active_trade_route.recalculation_blocker.return_value=(
            "Quedan 24 toneladas por vender."
        )
        center._start_fixed_voice_response=Mock()
        center.navigation_manager=Mock()
        cache=Mock()

        center._calculate_freyja_trade("expedition",cache)

        center._start_fixed_voice_response.assert_called_once_with(
            "Quedan 24 toneladas por vender.",officer="FREYJA"
        )
        cache.opportunities.assert_not_called()

    def test_freyja_sends_credit_amount_to_voice_without_separators(self):
        plan=SimpleNamespace(
            units=24,
            estimated_profit=359520,
            stale_hours=1,
            opportunity=SimpleNamespace(
                commodity="silver",buy_station="Compra",buy_system="A",
                sell_station="Venta",sell_system="B",jumps=1,
            ),
        )

        answer=CommandCenter._quick_trade_voice_summary(plan)

        self.assertIn("359520 créditos",answer)
        self.assertNotIn("359,520",answer)

    def test_fixed_response_uses_requested_officer(self):
        center=CommandCenter.__new__(CommandCenter)
        center.config=SimpleNamespace()
        center._voice_busy=threading.Event(); center._voice_busy.set()
        center.wake_listener=Mock()
        with patch("core.command_center.OfficerVoiceService") as service:
            center._run_fixed_voice_response("HEIMDALL","Ruta calculada.")
        service.return_value.speak.assert_called_once_with("HEIMDALL","Ruta calculada.")
        center.wake_listener.resume.assert_called_once()

    def test_freyja_trade_request_opens_four_option_menu_and_arms_reply(self):
        center=CommandCenter.__new__(CommandCenter)
        center._pending_freyja_trade_menu=False
        center.commander_state=SimpleNamespace(fid="",commander_name="")
        center._last_voice_question=""
        center.command_memory=Mock()
        center._start_fixed_voice_response=Mock()

        center._start_voice_response("Freyja, quiero comerciar")

        self.assertTrue(center._pending_freyja_trade_menu)
        answer=center._start_fixed_voice_response.call_args.args[0]
        self.assertIn("cuatro modelos",answer)
        self.assertIn("ruta r\u00e1pida",answer)
        self.assertIn("tres estaciones",answer)
        self.assertIn("treinta saltos",answer)
        self.assertIn("Powerplay",answer)
        self.assertEqual(
            center._start_fixed_voice_response.call_args.kwargs,
            {"officer":"FREYJA","arm_after":True},
        )

    def test_odin_hands_trade_request_to_freyja_without_saying_her_name(self):
        center=CommandCenter.__new__(CommandCenter)
        center._pending_freyja_trade_menu=False
        center.commander_state=SimpleNamespace(fid="",commander_name="")
        center._last_voice_question=""
        center.command_memory=Mock()
        center._start_fixed_voice_response=Mock()

        center._start_voice_response("quiero comerciar")

        self.assertTrue(center._pending_freyja_trade_menu)
        self.assertEqual(
            center._start_fixed_voice_response.call_args.kwargs["officer"],
            "FREYJA",
        )
        center.command_memory.remember.assert_called_once_with(
            "default", "quiero comerciar", "freyja_trade_menu", {}
        )

    def test_observed_whisper_trade_confusion_is_handed_to_freyja(self):
        center=CommandCenter.__new__(CommandCenter)
        center._pending_freyja_trade_menu=False
        center.commander_state=SimpleNamespace(fid="",commander_name="")
        center._last_voice_question=""
        center.command_memory=Mock()
        center._start_fixed_voice_response=Mock()

        center._start_voice_response("y el fin de la pr\u00f3xima vez")

        self.assertTrue(center._pending_freyja_trade_menu)
        self.assertEqual(
            center._start_fixed_voice_response.call_args.kwargs["officer"],
            "FREYJA",
        )

    def test_new_trade_confusions_are_learned_as_freyja_menu(self):
        for transcript in ("y gaseer comercio", "vale bien"):
            center=CommandCenter.__new__(CommandCenter)
            center._pending_freyja_trade_menu=False
            center.commander_state=SimpleNamespace(fid="F123",commander_name="")
            center._last_voice_question=""
            center.command_memory=Mock()
            center._start_fixed_voice_response=Mock()

            center._start_voice_response(transcript)

            center.command_memory.remember.assert_called_once_with(
                "F123",transcript,"freyja_trade_menu",{}
            )
            self.assertTrue(center._pending_freyja_trade_menu)

    def test_freyja_trade_request_accepts_natural_variants(self):
        self.assertTrue(CommandCenter._is_freyja_trade_request("quiero comerciar"))
        self.assertTrue(CommandCenter._is_freyja_trade_request("vamos a hacer comercio"))
        self.assertTrue(CommandCenter._is_freyja_trade_request("quiero comprar y vender"))
        self.assertFalse(CommandCenter._is_freyja_trade_request("cu\u00e1nto combustible tengo"))
        self.assertTrue(CommandCenter._is_freyja_trade_request("y gaseer comercio"))
        self.assertTrue(CommandCenter._is_freyja_trade_request("vale bien"))
        learned=CommandCenter._command_from_text("quiero comerciar")
        self.assertEqual(learned.intent,"freyja_trade_menu")

    def test_freyja_trade_request_accepts_english_and_portuguese(self):
        for command in (
            "I want to trade", "let's trade", "start trading",
            "quero comerciar", "vamos comerciar", "fazer comercio",
        ):
            with self.subTest(command=command):
                self.assertTrue(CommandCenter._is_freyja_trade_request(command))
                self.assertEqual(
                    CommandCenter._command_from_text(command).intent,
                    "freyja_trade_menu",
                )

    def test_freyja_recognizes_trade_progress_questions(self):
        self.assertTrue(CommandCenter._is_freyja_trade_status_request(
            "estado de la ruta comercial"
        ))
        self.assertTrue(CommandCenter._is_freyja_trade_status_request(
            "qué tengo que comprar"
        ))
        self.assertTrue(CommandCenter._is_freyja_trade_status_request(
            "cuál es el siguiente tramo"
        ))
        self.assertTrue(CommandCenter._is_freyja_trade_status_request(
            "repetí la instrucción"
        ))
        self.assertTrue(CommandCenter._is_freyja_trade_cancel_request(
            "cancelá la ruta comercial"
        ))
        self.assertFalse(CommandCenter._is_freyja_trade_cancel_request(
            "cancelá la ruta de neutrones"
        ))
        self.assertTrue(CommandCenter._is_freyja_trade_cancel_confirmation(
            "confirmo la cancelación comercial"
        ))
        self.assertTrue(CommandCenter._is_freyja_trade_recalculate_request(
            "recalculá la ruta comercial"
        ))
        self.assertFalse(CommandCenter._is_freyja_trade_recalculate_request(
            "recalculá la ruta de neutrones"
        ))

    def test_freyja_reports_confirmed_trade_ledger_without_number_separators(self):
        self.assertTrue(CommandCenter._is_freyja_trade_ledger_request(
            "cuánto beneficio llevo comerciando"
        ))
        self.assertTrue(CommandCenter._is_freyja_trade_ledger_request(
            "cuánto invertí en comercio"
        ))
        answer=CommandCenter._freyja_ledger_voice_summary(
            TradeSummary(48,24,801984,1161504,359520,24)
        )
        self.assertIn("359520 créditos",answer)
        self.assertIn("801984 créditos",answer)
        self.assertNotIn("359,520",answer)

    def test_freyja_pending_menu_starts_selected_calculation_without_wake_word(self):
        center=CommandCenter.__new__(CommandCenter)
        center._pending_freyja_trade_menu=True
        center._start_freyja_trade_calculation=Mock()

        center._start_voice_response("la cuarta, Powerplay")

        self.assertFalse(center._pending_freyja_trade_menu)
        center._start_freyja_trade_calculation.assert_called_once_with("powerplay")

    def test_explicit_option_two_survives_lost_menu_state(self):
        center=CommandCenter.__new__(CommandCenter)
        center._pending_freyja_trade_menu=False
        center._start_freyja_trade_calculation=Mock()

        center._start_voice_response("la opci\u00f3n 2")

        center._start_freyja_trade_calculation.assert_called_once_with("three_station")

    def test_freyja_menu_understands_all_four_spoken_choices(self):
        self.assertEqual(CommandCenter._freyja_trade_selection("uno"),"quick")
        self.assertEqual(CommandCenter._freyja_trade_selection("circuito"),"three_station")
        self.assertEqual(CommandCenter._freyja_trade_selection("treinta saltos"),"expedition")
        self.assertEqual(CommandCenter._freyja_trade_selection("m\u00e9ritos"),"powerplay")

    def test_fixed_response_can_arm_direct_follow_up(self):
        center=CommandCenter.__new__(CommandCenter)
        center.config=SimpleNamespace()
        center._voice_busy=threading.Event(); center._voice_busy.set()
        center.wake_listener=Mock()
        with patch("core.command_center.OfficerVoiceService"):
            center._run_fixed_voice_response("FREYJA","Elija una opci\u00f3n.",arm_after=True)
        center.wake_listener.arm.assert_called_once()
        center.wake_listener.resume.assert_called_once()

    def test_unclear_command_allows_only_one_retry(self):
        center=CommandCenter.__new__(CommandCenter)
        center._voice_retry_pending=False
        center.wake_listener=Mock()
        center._start_fixed_voice_response=Mock()

        center._handle_unclear_voice_command()

        self.assertTrue(center._voice_retry_pending)
        center._start_fixed_voice_response.assert_called_once_with(
            "No entendí la orden. Repítala, comandante.", arm_after=True
        )

        center._start_fixed_voice_response.reset_mock()
        center._handle_unclear_voice_command()

        self.assertFalse(center._voice_retry_pending)
        center.wake_listener.armed.clear.assert_called_once_with()
        center._start_fixed_voice_response.assert_called_once_with(
            "No pude reconocer la orden. Cierro la escucha, comandante."
        )

    def test_freyja_announces_selected_mode_before_calculating(self):
        expected = {
            "quick": ("Opción uno", "ruta rápida"),
            "three_station": ("Opción dos", "tres estaciones"),
            "expedition": ("Opción tres", "expedición comercial"),
            "powerplay": ("Opción cuatro", "territorio Powerplay"),
        }
        for selection, phrases in expected.items():
            with self.subTest(selection=selection):
                center=CommandCenter.__new__(CommandCenter)
                center.config=SimpleNamespace()
                center._voice_busy=threading.Event(); center._voice_busy.set()
                center.wake_listener=Mock()
                with patch("core.command_center.OfficerVoiceService") as service:
                    center._announce_freyja_trade_start(selection)
                officer, announcement = service.return_value.speak.call_args.args
                self.assertEqual(officer, "FREYJA")
                self.assertIn(phrases[0], announcement)
                self.assertIn(phrases[1], announcement)
                self.assertIn("Comienzo", announcement)
                self.assertFalse(center._voice_busy.is_set())
                center.wake_listener.resume.assert_called_once()

    def test_wake_acknowledgement_uses_odin_and_resumes_listener(self):
        center=CommandCenter.__new__(CommandCenter)
        center.config=SimpleNamespace()
        center._voice_busy=threading.Event(); center._voice_busy.set()
        center._wake_acknowledgement_index=0
        center._wake_acknowledgement_lock=threading.Lock()
        center.wake_listener=Mock()
        with patch("core.command_center.OfficerVoiceService") as service:
            center._run_wake_acknowledgement()
        service.return_value.speak.assert_called_once_with("ODIN", "Sí, comandante?")
        self.assertFalse(center._voice_busy.is_set())
        center.wake_listener.resume.assert_called_once()

    def test_wake_acknowledgements_rotate_without_immediate_repetition(self):
        center=CommandCenter.__new__(CommandCenter)
        center._wake_acknowledgement_index=0
        center._wake_acknowledgement_lock=threading.Lock()

        phrases=[
            center._next_wake_acknowledgement()
            for _ in CommandCenter.WAKE_ACKNOWLEDGEMENTS
        ]

        self.assertEqual(tuple(phrases), CommandCenter.WAKE_ACKNOWLEDGEMENTS)
        self.assertEqual(
            center._next_wake_acknowledgement(),
            CommandCenter.WAKE_ACKNOWLEDGEMENTS[0],
        )

    def test_processing_messages_match_the_requested_context(self):
        self.assertEqual(
            CommandCenter._processing_message_for("qué biologías hay"),
            "Consultando los registros científicos.",
        )
        self.assertEqual(
            CommandCenter._processing_message_for("cuánto combustible tengo"),
            "Revisando los datos del comandante.",
        )
        self.assertEqual(
            CommandCenter._processing_message_for("datos de este sistema"),
            "Revisando la base de datos.",
        )

    def test_rejects_garbled_short_transcripts_but_accepts_real_orders(self):
        self.assertFalse(CommandCenter._is_credible_voice_question("Olíden"))
        self.assertFalse(CommandCenter._is_credible_voice_question("Táatió"))
        self.assertTrue(CommandCenter._is_credible_voice_question("¿Estás activo?"))
        self.assertTrue(CommandCenter._is_credible_voice_question("combustible"))

    def test_processing_message_signals_completion_without_resuming_listener(self):
        center=CommandCenter.__new__(CommandCenter)
        center.config=SimpleNamespace()
        center.wake_listener=Mock()
        completed=threading.Event()
        with patch("core.command_center.OfficerVoiceService") as service:
            center._run_processing_message("ODIN", "Procesando.", completed)
        service.return_value.speak.assert_called_once_with("ODIN", "Procesando.")
        self.assertTrue(completed.is_set())
        center.wake_listener.resume.assert_not_called()

    def test_answer_never_repeats_full_current_system_name(self):
        center=CommandCenter.__new__(CommandCenter)
        center.commander_state=SimpleNamespace(current_system="Synuefua QF-L d9-25")
        center.scientific_context=Mock()
        center.scientific_context.system_predictions.return_value={
            "Synuefua QF-L d9-25 1": ("Bacterium",)
        }

        answer=center._sanitize_current_system_references(
            "hay exobiología en este sistema",
            "Sí, en Synuefua QF-L d9-25 1.",
        )

        self.assertEqual(answer, "Sí, en planeta 1.")

        geology=center._sanitize_current_system_references(
            "hay geología en este sistema",
            "No tengo información geológica de Synuefua QF-L d9-25."
        )
        self.assertEqual(
            geology,
            "No tengo información geológica de este sistema.",
        )

        named=center._sanitize_current_system_references(
            "en qué sistema estoy",
            "Estás en Synuefua QF-L d9-25.",
        )
        self.assertEqual(named, "Estás en Synuefua QF-L d9-25.")

    def test_trade_mining_and_network_commands_support_english_and_portuguese(self):
        self.assertTrue(CommandCenter._is_freyja_trade_request("I want to trade"))
        self.assertTrue(CommandCenter._is_freyja_trade_request("Quero comerciar"))
        self.assertEqual(CommandCenter._freyja_trade_selection("option two"), "three_station")
        self.assertEqual(CommandCenter._freyja_trade_selection("opção três"), "expedition")
        self.assertEqual(CommandCenter._brokk_mining_request("I want to mine painite"), "painite")
        self.assertEqual(CommandCenter._brokk_mining_request("Quero minerar painita"), "painita")
        self.assertTrue(CommandCenter._is_brokk_status_request("mining status"))
        self.assertTrue(CommandCenter._is_brokk_sale_request("where to sell mining cargo"))
        self.assertTrue(CommandCenter._is_eddn_status_request("EDDN transmission status"))
        self.assertTrue(CommandCenter._is_freyja_trade_cancel_request("cancel trade route"))
        self.assertTrue(CommandCenter._is_freyja_trade_recalculate_request("recalculate trade route"))
        self.assertTrue(CommandCenter._is_fsd_injection_status_request("FSD injection status"))
        self.assertTrue(CommandCenter._is_fsd_injection_status_request("síntese de salto FSD"))
        self.assertEqual(CommandCenter._fsd_injection_distance_request("jump 85 light-years"), 85.0)
        self.assertEqual(CommandCenter._fsd_injection_distance_request("alcançar 92 anos-luz"), 92.0)
        self.assertTrue(CommandCenter._is_route_injection_status_request("route FSD synthesis"))
        self.assertTrue(CommandCenter._is_route_injection_status_request("rota de injeção FSD"))
        self.assertTrue(CommandCenter._is_fsd_injection_authorization("authorize FSD injection"))
        self.assertTrue(CommandCenter._is_fsd_injection_authorization("aprovo a injeção FSD"))
        self.assertTrue(CommandCenter._is_memory_confirmation("that is correct"))
        self.assertTrue(CommandCenter._is_memory_confirmation("isso está certo"))
        self.assertTrue(CommandCenter._is_memory_forget("forget that command"))
        self.assertTrue(CommandCenter._is_memory_forget("esqueça essa ordem"))
        self.assertEqual(CommandCenter._memory_correction("I meant request docking"), "request docking")
        self.assertEqual(CommandCenter._memory_correction("eu quis dizer luz noturna"), "luz noturna")

    def test_current_system_reference_uses_selected_language(self):
        center = CommandCenter.__new__(CommandCenter)
        center.config = SimpleNamespace(language="en-US")
        center.commander_state = SimpleNamespace(current_system="Synuefua QF-L d9-25")
        center.scientific_context = Mock()
        center.scientific_context.system_predictions.return_value = {}

        answer = center._sanitize_current_system_references(
            "is there biology here",
            "There is biology in Synuefua QF-L d9-25.",
        )

        self.assertEqual(answer, "There is biology in this system.")

if __name__=="__main__": unittest.main()
