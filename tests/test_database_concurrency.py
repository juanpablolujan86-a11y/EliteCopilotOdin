from pathlib import Path
import tempfile
import unittest

from core.database import DatabaseManager


class DatabaseConcurrencyTests(unittest.TestCase):
    def test_connections_use_wal_and_busy_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = DatabaseManager(Path(directory))
            second = DatabaseManager(Path(directory))
            first.connect()
            second.connect()
            try:
                self.assertEqual(
                    first.query("PRAGMA journal_mode")[0][0].casefold(), "wal"
                )
                self.assertGreaterEqual(
                    int(second.query("PRAGMA busy_timeout")[0][0]), 30_000
                )
                first.execute("CREATE TABLE sample (value INTEGER)")
                first.execute("INSERT INTO sample VALUES (1)")
                self.assertEqual(second.query("SELECT value FROM sample")[0][0], 1)
            finally:
                second.disconnect()
                first.disconnect()


if __name__ == "__main__":
    unittest.main()
