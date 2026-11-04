import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from thorgor.game_manager.native_completion import CompletionTracker
from thorgor.master.accounts import AccountStore
from thorgor.master.match_completion import completion_updates


class CompletionTests(unittest.TestCase):
    def test_only_current_authenticated_match_can_be_released(self):
        state = {"server_session": "test-session", "match_id": 7,
                 "match_host_key": "old-key", "match_host_account_id": 1}
        for session, match_id in (("", 7), ("wrong", 7), ("test-session", 6), ("test-session", 0)):
            with self.subTest(session=session, match_id=match_id), self.assertRaises(ValueError):
                completion_updates(state, session, match_id)
        updates = completion_updates(state, "test-session", 7)
        self.assertEqual((updates["match_id"], updates["match_host_key"], updates["match_host_account_id"]),
                         (0, "", 0))
        self.assertEqual(state["match_id"], 7)
        self.assertEqual(completion_updates({**state, **updates}, "test-session", 7), {})
        with self.assertRaises(ValueError):
            completion_updates({**state, "match_id": 8}, "test-session", 7)

    def test_active_departure_or_changed_native_identity_cannot_complete_match(self):
        tracker = CompletionTracker()
        tracker.observe(10, 0x10000, 7, "test-session", 6)
        self.assertFalse(tracker.cleared(10, 0x10000, 7, "test-session"))
        tracker.observe(10, 0x10000, 7, "test-session", 7)
        for pid, game, match_id, session in ((11, 0x10000, 7, "test-session"),
                    (10, 0x20000, 7, "test-session"), (10, 0x10000, 8, "test-session"),
                    (10, 0x10000, 7, "new-session")):
            self.assertFalse(tracker.cleared(pid, game, match_id, session))
        self.assertTrue(tracker.cleared(10, 0x10000, 7, "test-session"))
        tracker.confirmed(10)
        self.assertFalse(tracker.cleared(10, 0x10000, 7, "test-session"))

    def test_hybrid_manager_session_is_accepted_only_without_a_server_session(self):
        state = {"manager_session": "test-manager", "match_id": 7}
        self.assertEqual(completion_updates(state, "test-manager", 7)["match_id"], 0)
        with self.assertRaises(ValueError):
            completion_updates({**state, "server_session": "test-server"}, "test-manager", 7)

    def test_expired_completion_observation_is_rejected(self):
        tracker = CompletionTracker()
        with patch("thorgor.game_manager.native_completion.time.monotonic", return_value=0):
            tracker.observe(10, 0x10000, 7, "test-session", 7)
        with patch("thorgor.game_manager.native_completion.time.monotonic", return_value=181):
            self.assertFalse(tracker.cleared(10, 0x10000, 7, "test-session"))

    def test_completion_removes_only_that_matchs_reconnect_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = AccountStore(Path(temporary) / "accounts.db")
            store.set_reconnect(1, "test-session", "127.0.0.1", 11236, 7)
            store.set_reconnect(2, "test-session", "127.0.0.1", 11236, 8)
            store.clear_match_reconnects(7)
            self.assertIsNone(store.get_reconnect(1))
            self.assertEqual(store.get_reconnect(2)["match_id"], 8)
