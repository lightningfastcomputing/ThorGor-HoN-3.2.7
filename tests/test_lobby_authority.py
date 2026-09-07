import struct
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from thorgor.master.host_authority import classify_match_host
from thorgor.protocols.admission import authorize_connect_c0, validate_c_conn_response
from thorgor.protocols.packet_decoding import parse_connect_c0
from thorgor.protocols.transport import make_authorized_local_c0


def connection(key="", marker=0):
    strings = ["", "player", "cookie", "127.0.0.1", key, ""]
    return (b"\0\0\1\xc0Heroes of Newerth\x003.2.7.1\0" + struct.pack("<IH", 123, 0)
            + b"".join(s.encode() + b"\0" for s in strings) + bytes([marker]) + b"tail")


class LobbyAuthorityTests(unittest.TestCase):
    def test_pending_owner_cannot_be_overwritten_by_joiner_or_wrong_key(self):
        state = {"pending_host_key": "key", "pending_host_account_id": 1}
        self.assertEqual(classify_match_host(1, "key", state), (True, False))
        for account, key in ((2, "key"), (2, "forged"), (2, ""), (1, "wrong")):
            self.assertEqual(classify_match_host(account, key, state), (False, False))

    def test_active_owner_requires_both_authenticated_account_and_key(self):
        state = {"match_id": 3, "match_host_key": "key", "match_host_account_id": 1}
        self.assertEqual(classify_match_host(1, "key", state), (True, False))
        for account, key in ((2, "key"), (2, ""), (1, "wrong"), (1, "")):
            self.assertEqual(classify_match_host(account, key, state), (False, False))

    def test_idle_create_flow_and_invalid_state(self):
        self.assertEqual(classify_match_host(1, "key", {}), (True, True))
        for account, key, state in ((0, "key", {}), (1, "", {}), (1, "key", {"match_id": "bad"})):
            self.assertEqual(classify_match_host(account, key, state), (False, False))

    def test_authenticated_decision_overrides_client_marker_without_changing_identity(self):
        for incoming in range(256):
            original = connection("creator-key", incoming)
            parsed = parse_connect_c0(original)
            for creator in (False, True):
                changed = make_authorized_local_c0(original, parsed, is_match_host=creator)
                self.assertEqual(changed[parsed.flag_offset], incoming & 0xFE | int(creator))
                self.assertEqual(changed[:parsed.flag_offset], original[:parsed.flag_offset])
                self.assertEqual(changed[parsed.flag_offset + 1:], original[parsed.flag_offset + 1:])
        for offset in (-1, 4):
            with self.assertRaises(ValueError):
                make_authorized_local_c0(bytes(4), SimpleNamespace(flag_offset=offset), is_match_host=False)

    def test_authorization_requires_unique_typed_decision_and_matching_cookie(self):
        response = b's:6:"cookie";s:6:"cookie";s:10:"account_id";i:2;s:11:"game_cookie";s:4:"abcd";'
        for decision in (0, 1):
            wire = response + f's:13:"is_match_host";i:{decision};'.encode()
            ok, _, creator = validate_c_conn_response(wire, "cookie")
            self.assertTrue(ok)
            self.assertEqual(creator, bool(decision))
            self.assertFalse(validate_c_conn_response(wire, "wrong-cookie")[0])
        for suffix in (b"", b's:13:"is_match_host";s:1:"1";', b's:13:"is_match_host";i:2;',
                       b's:13:"is_match_host";i:0;s:13:"is_match_host";i:1;'):
            self.assertEqual(validate_c_conn_response(response + suffix, "cookie")[::2], (False, False))

    def test_master_response_to_native_marker_for_creator_and_joiner(self):
        from thorgor.master import server
        state = {}
        response = {}
        handler = object.__new__(server.Handler)
        handler.headers = {}
        handler.client_address = ("127.0.0.1", 1)
        handler.path = "/server_requester.php"
        handler.send_php = lambda payload: response.update(payload)
        identity = {"account_id": 1, "nickname": "Creator", "cookie": "cookie", "game_cookie": "abcd"}

        def update(**values):
            state.update(values)
            return state.copy()

        with patch.object(server, "ACCOUNTS", object()), patch.object(server, "client_auth_response", lambda *_: identity.copy()), \
             patch.object(server, "v31_read_state", lambda: state.copy()), patch.object(server, "v31_update_state", update), \
             patch.object(server, "server_log"), patch.object(server, "capture", return_value=Path("fixture.json")):
            for account, key, creator in ((1, "key", True), (2, "", False), (2, "key", False)):
                identity["account_id"] = account
                params = {"f": ["c_conn"], "cookie": ["cookie"], "host_key": [key]}
                response.clear()
                handler.handle_server_requester(b"", params)
                wire = server.php_serialize(response)
                raw = connection(key, marker=0xFF)
                parsed = parse_connect_c0(raw)
                with patch("thorgor.protocols.admission._post", return_value=wire):
                    approved, _, decision = authorize_connect_c0(parsed, "http://localhost", 1)
                self.assertTrue(approved)
                self.assertEqual(decision, creator)
                rewritten = make_authorized_local_c0(raw, parsed, is_match_host=decision)
                self.assertEqual(rewritten[parsed.flag_offset] & 1, int(creator))
                self.assertEqual(state["pending_host_account_id"], 1)
