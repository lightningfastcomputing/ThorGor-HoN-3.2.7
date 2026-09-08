import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from thorgor.master.accounts import AccountStore
from thorgor.master import server


class ReconnectTests(unittest.TestCase):
    def test_reconnect_record_round_trips_and_clears(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = AccountStore(Path(temporary) / "accounts.db")
            account = store.add_or_update("player", "password")
            store.set_reconnect(account.account_id, "server-session", "192.168.1.20", 11236, 42)
            self.assertEqual(store.get_reconnect(account.account_id), {
                "server_session": "server-session",
                "ip": "192.168.1.20",
                "port": 11236,
                "match_id": 42,
            })
            store.clear_reconnects(account.account_id)
            self.assertIsNone(store.get_reconnect(account.account_id))

    def test_login_exposes_only_the_active_match_reconnect(self):
        reconnect = {"server_session": "session", "ip": "192.168.1.20",
                     "port": 11236, "match_id": 42}
        store = SimpleNamespace(
            get_reconnect=lambda account_id: reconnect,
            list_friends=lambda account_id: [],
            pending_friend_notifications=lambda account_id: [],
        )
        session = SimpleNamespace(account_id=7, M2=b"proof", nickname="player", username="player")
        with patch.object(server, "v31_read_state", return_value={"match_id": 42}):
            payload = server.success_payload(session, "cookie", store)
        self.assertEqual(payload["reconnect"], {
            "ip": "192.168.1.20", "port": 11236, "match_id": 42,
        })
        with patch.object(server, "v31_read_state", return_value={"match_id": 43}):
            payload = server.success_payload(session, "cookie", store)
        self.assertNotIn("reconnect", payload)

    def test_native_registration_is_validated_and_uses_public_gateway(self):
        recorded = []
        store = SimpleNamespace(set_reconnect=lambda *args: recorded.append(args))
        response = {}
        handler = object.__new__(server.Handler)
        handler.headers = {}
        handler.client_address = ("127.0.0.1", 1)
        handler.path = "/server_requester.php"
        handler.send_php = lambda payload: response.update(payload)
        params = {"f": ["set_reconnect"], "session": ["server-session"],
                  "account_id": ["7"], "ip": ["127.0.0.1"], "port": ["11235"],
                  "match_id": ["42"]}
        with patch.object(server, "ACCOUNTS", store), \
             patch.object(server, "v31_read_state", return_value={
                 "server_session": "server-session", "match_id": 42,
             }), patch.object(server, "server_log"), \
             patch.object(server, "capture", return_value=Path("fixture.json")), \
             patch.object(server.CONFIG, "server_list_ip", "192.168.1.20"), \
             patch.object(server.CONFIG, "server_list_port", 11236):
            handler.handle_server_requester(b"", params)
        self.assertEqual(response["success"], 1)
        self.assertEqual(recorded, [(7, "server-session", "192.168.1.20", 11236, 42)])


if __name__ == "__main__":
    unittest.main()
