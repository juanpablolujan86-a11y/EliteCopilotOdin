import json
import tempfile
import unittest
from pathlib import Path

from core.journal_reader import JournalReader
from core.journal_watcher import JournalWatcher
from core.processors.commander_state_updater import CommanderStateUpdater
from state.commander_state import CommanderState


class JournalBootstrapTestCase(unittest.TestCase):
    def test_watcher_replays_new_journal_from_load_game(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "Journal.old.log"
            new = root / "Journal.new.log"
            old.write_text('{"event":"FSDJump","StarSystem":"Old"}\n', encoding="utf-8")
            new.write_text(
                '{"event":"Commander","Name":"Zorro"}\n'
                '{"event":"LoadGame","Credits":765738062}\n',
                encoding="utf-8",
            )
            watcher = JournalWatcher(old)
            watcher.start()

            watcher.follow(new, replay_existing=True)
            events = watcher.poll()

        self.assertEqual([event["event"] for event in events], ["Commander", "LoadGame"])
        self.assertEqual(events[-1]["Credits"], 765738062)

    def test_current_system_is_restored_without_replaying_events(self) -> None:
        events = [
            {
                "timestamp": "2026-07-31T23:00:00Z",
                "event": "FSDJump",
                "StarSystem": "Sistema anterior",
                "SystemAddress": 1,
            },
            {
                "timestamp": "2026-08-01T00:54:00Z",
                "event": "FSDJump",
                "StarSystem": "Hegai SS-K d8-4",
                "SystemAddress": 149224998987,
                "Body": "Hegai SS-K d8-4 A",
                "FuelLevel": 119.08,
            },
            {
                "timestamp": "2026-08-01T01:02:02Z",
                "event": "Scan",
                "StarSystem": "Hegai SS-K d8-4",
                "SystemAddress": 149224998987,
                "BodyName": "Hegai SS-K d8-4 B 2",
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "Journal.test.log"
            journal.write_text(
                "\n".join(json.dumps(event) for event in events),
                encoding="utf-8",
            )
            context = JournalReader(Path(directory)).current_system_context(
                journal
            )

        state = CommanderState()
        CommanderStateUpdater(state).restore_context(context)

        self.assertEqual(state.current_system, "Hegai SS-K d8-4")
        self.assertEqual(state.system_address, 149224998987)
        self.assertEqual(state.current_body, "Hegai SS-K d8-4 B 2")
        self.assertEqual(state.fuel_level, 119.08)

    def test_current_system_events_ignore_next_jump_target(self) -> None:
        events = [
            {
                "event": "FSDJump",
                "StarSystem": "Sistema actual",
                "SystemAddress": 10,
            },
            {
                "event": "Scan",
                "StarSystem": "Sistema actual",
                "SystemAddress": 10,
                "BodyName": "Sistema actual 1",
            },
            {
                "event": "FSDTarget",
                "Name": "Sistema siguiente",
                "SystemAddress": 20,
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "Journal.test.log"
            journal.write_text(
                "\n".join(json.dumps(event) for event in events),
                encoding="utf-8",
            )
            reader = JournalReader(Path(directory))
            current_events = reader.current_system_events(journal)
            context = reader.current_system_context(journal)

        self.assertEqual(len(current_events), 3)
        self.assertEqual(context["StarSystem"], "Sistema actual")
        self.assertEqual(context["SystemAddress"], 10)
        self.assertEqual(context["Body"], "Sistema actual 1")

    def test_commander_and_ship_are_restored_from_journal(self) -> None:
        events = [
            {"event": "Commander", "FID": "F123", "Name": "Zorro"},
            {
                "event": "LoadGame", "Commander": "Zorro", "Credits": 3000,
                "Loan": 0, "Ship": "Explorer_NX", "Ship_Localised": "Caspian Explorer",
                "ShipName": "Thor", "ShipIdent": "ZDJ-2", "FuelLevel": 120,
                "FuelCapacity": 128,
            },
            {"event": "Statistics", "Bank_Account": {"Current_Wealth": 5000}},
            {
                "event": "Powerplay", "Power": "Li Yong-Rui", "Rank": 25,
                "Merits": 175715, "TimePledged": 50438411,
            },
            {"event": "PowerplayMerits", "PowerplayMerits": 175900},
            {"event": "FSDJump", "StarSystem": "Sol", "SystemAddress": 1},
        ]
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "Journal.test.log"
            journal.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
            reader = JournalReader(Path(directory))
            profile = reader.commander_context(journal)

        state = CommanderState()
        updater = CommanderStateUpdater(state)
        for event in profile:
            updater.handle_profile_event(event)

        self.assertEqual(state.commander_name, "Zorro")
        self.assertEqual(state.credits, 3000)
        self.assertEqual(state.current_wealth, 5000)
        self.assertEqual(state.ship_name, "Thor")
        self.assertEqual(state.ship_type_localised, "Caspian Explorer")
        self.assertEqual(state.powerplay_power, "Li Yong-Rui")
        self.assertEqual(state.powerplay_rank, 25)
        self.assertEqual(state.powerplay_merits, 175900)

    def test_expedition_sales_increase_known_credit_balance(self) -> None:
        state = CommanderState(credits=1000)
        updater = CommanderStateUpdater(state)
        updater.handle_sale({"event": "SellExplorationData", "TotalEarnings": 250})
        updater.handle_sale({
            "event": "SellOrganicData",
            "BioData": [{"Value": 100, "Bonus": 400}],
        })
        self.assertEqual(state.credits, 1750)

    def test_carrier_bank_transfer_replaces_player_balance(self) -> None:
        state = CommanderState(credits=765_738_062)
        updater = CommanderStateUpdater(state)
        updater.handle_balance_event({
            "event": "CarrierBankTransfer",
            "Deposit": 650_000_000,
            "PlayerBalance": 115_712_464,
            "CarrierBalance": 1_054_132_425,
        })
        self.assertEqual(state.credits, 115_712_464)

    def test_latest_player_balance_prefers_newer_carrier_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "Journal.test.log"
            journal.write_text(
                '{"event":"LoadGame","Credits":765738062}\n'
                '{"event":"CarrierBankTransfer","PlayerBalance":115712464}\n',
                encoding="utf-8",
            )
            event = JournalReader(Path(directory)).latest_player_balance_event()

        self.assertEqual(event["event"], "CarrierBankTransfer")
        self.assertEqual(event["PlayerBalance"], 115_712_464)
