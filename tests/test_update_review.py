import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from core.database import DatabaseManager
from powerplay.advisor import SpanshPowerplaySearchClient
from services.updates import check_for_update, RELEASES_URL


class ReviewRegressionTests(unittest.TestCase):
    def test_failed_commit_does_not_break_next_write(self):
        with tempfile.TemporaryDirectory() as directory:
            db = DatabaseManager(Path(directory))
            db.connection = Mock()
            db.connection.commit.side_effect = [RuntimeError("disk"), None]
            with self.assertRaises(RuntimeError):
                with db.transaction():
                    pass
            self.assertEqual(db._transaction_depth, 0)
            db.connection.rollback.assert_called_once()
            db.execute("INSERT INTO sample VALUES (1)")
            self.assertEqual(db.connection.commit.call_count, 2)

    def test_contested_requires_participation(self):
        rows = [
            {"name": "Other", "power_state": "Contested", "power": ["Denton Patreus"]},
            {"name": "Ours", "power_state": "Contested", "power": ["Li Yong-Rui"]},
        ]
        found = SpanshPowerplaySearchClient._records(rows, "Li Yong-Rui", 250)
        self.assertEqual([x.system for x in found], ["Ours"])

    def test_update_selection(self):
        session = Mock()
        def release(tag, **kwargs):
            return dict(tag_name=tag, html_url=RELEASES_URL + "/tag/" + tag, **kwargs)
        session.get.return_value.json.return_value = [
            release("v0.8.1-beta-pre-IA", prerelease=True),
            release("v0.8.3-beta", prerelease=True),
            release("v9.0.0", draft=True),
            dict(tag_name="v8.0.0", html_url="https://example.com"),
        ]
        self.assertEqual(check_for_update("0.8.2-beta", session).version, "v0.8.3-beta")
        self.assertIsNone(check_for_update("0.8.3-beta", session))
        self.assertIsNone(check_for_update("0.8.2", session))

    def test_same_version_and_stable_upgrade(self):
        session = Mock()
        session.get.return_value.json.return_value = [
            dict(tag_name="v0.8.2", html_url=RELEASES_URL + "/tag/v0.8.2")
        ]
        self.assertIsNotNone(check_for_update("0.8.2-beta", session))
        self.assertIsNone(check_for_update("0.8.2", session))

    def test_network_failure_propagates_to_background_handler(self):
        session = Mock()
        session.get.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            check_for_update(session=session)
