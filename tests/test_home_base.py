import json
import os
import tempfile
import unittest
from pathlib import Path

from core.journal_reader import JournalReader
from heimdall.home_base import HomeBaseManager


STORED_SHIPS = {
    "event": "StoredShips",
    "StarSystem": "GCRV 1568",
    "StationName": "Cernan Dock",
    "ShipsHere": [{"ShipID": 1}, {"ShipID": 2}, {"ShipID": 3}],
    "ShipsRemote": [
        {"ShipID": 4, "StarSystem": "Shinrarta Dezhra"},
        {"ShipID": 5, "StarSystem": "Shinrarta Dezhra"},
        {"ShipID": 6, "StarSystem": "Shinrarta Dezhra"},
        {"ShipID": 7, "StarSystem": "Lembava"},
    ],
}


class HomeBaseTests(unittest.TestCase):
    def test_infers_base_and_prefers_current_station_on_tie(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = HomeBaseManager(Path(directory))
            base = manager.update_from_stored_ships(STORED_SHIPS)
            restored = HomeBaseManager(Path(directory)).load()

        self.assertEqual(base.system, "GCRV 1568")
        self.assertEqual(base.station, "Cernan Dock")
        self.assertEqual(base.stored_ships, 3)
        self.assertEqual(restored, base)

    def test_reader_finds_latest_stored_ships_across_journals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "Journal.1.log"
            new = root / "Journal.2.log"
            old.write_text(json.dumps({**STORED_SHIPS, "StarSystem": "Old"}), encoding="utf-8")
            new.write_text(
                "\n".join((json.dumps(STORED_SHIPS), json.dumps({"event": "Scan"}))),
                encoding="utf-8",
            )
            os.utime(old, (1, 1))
            os.utime(new, (2, 2))
            event = JournalReader(root).latest_stored_ships_event()

        self.assertEqual(event["StarSystem"], "GCRV 1568")


if __name__ == "__main__":
    unittest.main()
