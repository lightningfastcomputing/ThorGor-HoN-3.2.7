import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import thorgor_hon_sandboxed_masterserver_v39 as backend


class BackendProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temporary_path = Path(self.temporary_directory.name)
        self.database_path = self.temporary_path / "accounts.db"
        self.store = backend.AccountStore(self.database_path)
        self.account = self.store.add_or_update("fixture-user", "unit-test-password", "Fixture User")
        self.authorization = self.store.register_game_authorization(self.account.account_id)
        self.saved_globals = {
            "ACCOUNTS": backend.ACCOUNTS,
            "V31_STATE_PATH": backend.V31_STATE_PATH,
            "LOG_PATH": backend.LOG_PATH,
            "SERVER_LOG_PATH": backend.SERVER_LOG_PATH,
            "SERVER_CAPTURE_DIR": backend.SERVER_CAPTURE_DIR,
        }
        backend.ACCOUNTS = self.store
        backend.V31_STATE_PATH = self.temporary_path / "registration-state.json"
        backend.LOG_PATH = self.temporary_path / "master.log"
        backend.SERVER_LOG_PATH = self.temporary_path / "server.log"
        backend.SERVER_CAPTURE_DIR = self.temporary_path / "captures"
        backend.v31_update_state(server_session="server-session")
        self.server = backend.Server(("127.0.0.1", 0), backend.Handler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)
        for name, value in self.saved_globals.items():
            setattr(backend, name, value)
        self.temporary_directory.cleanup()

    def post_server_request(self, fields):
        body = urlencode(fields).encode("ascii")
        request = Request(
            f"http://127.0.0.1:{self.server.server_port}/server_requester.php",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            return response.read()

    def test_start_game_allocates_persistent_positive_match_ids(self):
        params = {
            "session": ["server-session"],
            "map": ["caldavar"],
            "version": ["3.2.7.1"],
            "mname": ["Bot Auto Match"],
        }
        first = backend.start_game_response(self.store, params, "server-session")
        second = backend.start_game_response(self.store, params, "server-session")

        self.assertGreater(first["match_id"], 0)
        self.assertEqual(second["match_id"], first["match_id"] + 1)
        self.assertEqual(first["is_recommended"], False)
        self.assertEqual(first["disabled_hero_list"], "")

    def test_native_start_game_can_reuse_the_published_lobby_match_id(self):
        params = {
            "session": ["server-session"],
            "map": ["caldavar"],
            "version": ["3.2.7.1"],
            "mname": ["Test Game"],
        }
        response = backend.start_game_response(
            self.store,
            params,
            "server-session",
            existing_match_id=417,
            existing_match_date="2026-08-09 13:00:00",
        )

        self.assertEqual(response["match_id"], 417)
        self.assertEqual(response["match_date"], "2026-08-09 13:00:00")

    def test_start_game_rejects_a_mismatched_server_session(self):
        with self.assertRaisesRegex(ValueError, "Invalid game-server session"):
            backend.start_game_response(
                self.store,
                {"session": ["wrong-session"]},
                "expected-session",
            )

    def test_client_auth_returns_the_kongor_identity_contract(self):
        response = backend.client_auth_response(
            self.store,
            {"cookie": [self.authorization.cookie], "ip": ["127.0.0.1"]},
        )

        self.assertEqual(response["cookie"], self.authorization.cookie)
        self.assertEqual(response["account_id"], self.account.account_id)
        self.assertEqual(response["nickname"], "Fixture User")
        self.assertTrue(response["game_cookie"])
        self.assertEqual(response["infos"][0]["acc_pub_skill"], 1500.0)
        self.assertEqual(response["my_upgrades"], ["h.AllHeroes.Hero"])

    def test_account_login_grants_the_lan_all_heroes_product(self):
        session = SimpleNamespace(
            M2=b"\x01\x02",
            account_id=self.account.account_id,
            nickname=self.account.nickname,
            username=self.account.username,
        )

        response = backend.success_payload(session)

        self.assertEqual(response["my_upgrades"], ["h.AllHeroes.Hero"])
        self.assertEqual(response["selected_upgrades"], [])

    def test_client_auth_rejects_an_unknown_cookie(self):
        with self.assertRaisesRegex(ValueError, "Invalid player cookie"):
            backend.client_auth_response(self.store, {"cookie": ["not-issued"]})

    def test_php_wire_keeps_match_and_account_ids_as_integers(self):
        start = backend.start_game_response(
            self.store,
            {"session": ["server-session"]},
            "server-session",
        )
        auth = backend.client_auth_response(
            self.store,
            {"cookie": [self.authorization.cookie]},
        )

        self.assertIn(b's:8:"match_id";i:', backend.php_serialize(start))
        self.assertIn(b's:10:"account_id";i:', backend.php_serialize(auth))
        self.assertIn(b's:11:"game_cookie";s:', backend.php_serialize(auth))
        self.assertIn(b's:13:"acc_pub_skill";d:1500.0;', backend.php_serialize(auth))
        self.assertIn(b's:16:"h.AllHeroes.Hero";', backend.php_serialize(auth))

    def test_http_start_game_route_returns_the_allocated_match(self):
        wire = self.post_server_request(
            {
                "f": "start_game",
                "session": "server-session",
                "map": "caldavar",
                "version": "3.2.7.1",
                "mname": "Bot Auto Match",
            }
        )

        self.assertIn(b's:8:"match_id";i:1;', wire)
        self.assertIn(b's:18:"disabled_hero_list";s:0:"";', wire)

    def test_http_client_auth_alias_returns_the_issued_identity(self):
        wire = self.post_server_request(
            {"f": "client_auth", "cookie": self.authorization.cookie, "ip": "127.0.0.1"}
        )

        self.assertIn(b's:10:"account_id";i:1;', wire)
        self.assertIn(b's:8:"nickname";s:12:"Fixture User";', wire)
        self.assertIn(b's:11:"game_cookie";s:32:', wire)

    def test_host_is_reserved_on_c_conn_and_published_on_final_create(self):
        backend.CONFIG.server_list_ip = "127.0.0.1"
        backend.CONFIG.server_list_port = 11236
        backend.v31_update_state(
            manager_control_connected=True,
            manager_associated=True,
            server_status=1,
            match_id=0,
        )

        wire = self.post_server_request(
            {
                "f": "c_conn",
                "cookie": self.authorization.cookie,
                "ip": "127.0.0.1",
                "host_key": "issued-create-key",
            }
        )

        self.assertIn(b's:10:"account_id";i:1;', wire)
        state = backend.v31_read_state()
        self.assertEqual(state.get("match_id", 0), 0)
        self.assertEqual(state["lifecycle"], "reserved")
        self.assertEqual(state["pending_host_account_id"], self.account.account_id)
        self.assertEqual(
            backend.match_server_list_payload(self.authorization.cookie, "90")["server_list"],
            {},
        )
        self.assertEqual(
            backend.match_server_list_payload(self.authorization.cookie, "10")["server_list"],
            {},
        )

        create_wire = self.post_server_request(
            {
                "f": "host_lobby",
                "cookie": self.authorization.cookie,
                "host_key": "issued-create-key",
                "version": "3.2.7.1",
                "mname": "asd",
                "map": "caldavar",
                "mode": "normal",
                "casual": "true",
                "options": "map:caldavar mode:normal casual:true",
            }
        )

        self.assertIn(b's:8:"match_id";i:1;', create_wire)
        state = backend.v31_read_state()
        self.assertEqual(state["match_id"], 1)
        self.assertEqual(state["lifecycle"], "lobby")
        self.assertEqual(state["match_name"], "asd")
        self.assertEqual(state["match_options"], "map:caldavar mode:normal casual:true")
        self.assertIn(
            backend.CONFIG.match_server_id,
            backend.match_server_list_payload(self.authorization.cookie, "10")["server_list"],
        )

    def test_abandoned_host_reservation_can_be_released(self):
        backend.v31_update_state(
            lifecycle="reserved",
            pending_host_key="issued-create-key",
            pending_host_account_id=self.account.account_id,
            pending_host_nickname=self.account.nickname,
            pending_host_reserved_at=backend.time.time(),
            match_id=0,
        )

        wire = self.post_server_request(
            {
                "f": "host_release",
                "cookie": self.authorization.cookie,
                "host_key": "issued-create-key",
            }
        )

        self.assertIn(b's:7:"success";i:1;', wire)
        state = backend.v31_read_state()
        self.assertEqual(state["pending_host_key"], "")
        self.assertEqual(state["lifecycle"], "idle")

    def test_joinable_game_list_uses_the_exact_kongor_join_row(self):
        backend.CONFIG.server_list_ip = "127.0.0.1"
        backend.CONFIG.server_list_port = 11236
        backend.CONFIG.match_server_id = 1
        backend.CONFIG.match_server_location = "USE"
        backend.v31_update_state(
            manager_control_connected=True,
            manager_associated=True,
            registered=True,
            server_status=1,
            match_id=7,
        )

        response = backend.match_server_list_payload(self.authorization.cookie, "10")

        self.assertEqual(
            response["server_list"][1],
            {
                "server_id": "1",
                "ip": "127.0.0.1",
                "port": "11236",
                "location": "USE",
                "class": "1",
            },
        )
        self.assertNotIn("acc_key", response)
        self.assertNotIn("acc_key_hash", response)

    def test_idle_vessel_is_create_only(self):
        backend.CONFIG.server_list_ip = "127.0.0.1"
        backend.CONFIG.server_list_port = 11236
        backend.v31_update_state(
            manager_control_connected=True,
            manager_associated=True,
            registered=True,
            server_status=1,
            match_id=0,
        )

        create_response = backend.match_server_list_payload(self.authorization.cookie, "90")
        join_response = backend.match_server_list_payload(self.authorization.cookie, "10")

        self.assertIn(backend.CONFIG.match_server_id, create_response["server_list"])
        self.assertEqual(join_response["server_list"], {})

    def test_active_lobby_is_join_only(self):
        backend.CONFIG.server_list_ip = "127.0.0.1"
        backend.CONFIG.server_list_port = 11236
        backend.v31_update_state(
            manager_control_connected=True,
            manager_associated=True,
            registered=True,
            server_status=1,
            match_id=42,
        )

        create_response = backend.match_server_list_payload(self.authorization.cookie, "90")
        join_response = backend.match_server_list_payload(self.authorization.cookie, "10")

        self.assertEqual(create_response["server_list"], {})
        self.assertIn(backend.CONFIG.match_server_id, join_response["server_list"])


if __name__ == "__main__":
    unittest.main()
