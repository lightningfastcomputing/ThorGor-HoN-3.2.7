import struct
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from thorgor.master.host_authority import classify_match_host
from thorgor.protocols.admission import authorize_connect_c0, validate_c_conn_response
from thorgor.protocols.packet_decoding import parse_connect_c0
from thorgor.protocols.transport import make_authorized_local_c0


def connection(key="", marker=0, account_id=7):
    strings = ["", "player", "cookie", "127.0.0.1", key, ""]
    return (b"\0\0\1\xc0Heroes of Newerth\x003.2.7.1\0" + struct.pack("<IH", 123, 0)
            + b"".join(s.encode() + b"\0" for s in strings) + bytes([marker])
            + struct.pack("<I", account_id) + b"tail")


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
                changed = make_authorized_local_c0(
                    original, parsed, is_match_host=creator, account_id=23
                )
                self.assertEqual(changed[parsed.flag_offset], incoming & 0xFC | int(creator))
                self.assertEqual(changed[:parsed.flag_offset], original[:parsed.flag_offset])
                self.assertEqual(
                    struct.unpack_from("<I", changed, parsed.account_id_offset)[0],
                    0x80000017,
                )
                self.assertEqual(changed[parsed.account_id_offset + 4:], original[parsed.account_id_offset + 4:])
        for offset in (-1, 4):
            with self.assertRaises(ValueError):
                make_authorized_local_c0(
                    bytes(4), SimpleNamespace(flag_offset=offset, account_id_offset=offset + 1),
                    is_match_host=False, account_id=1
                )

    def test_gateway_can_assign_a_stable_native_connection_id(self):
        original = connection("", marker=0)
        parsed = parse_connect_c0(original)
        changed = make_authorized_local_c0(
            original, parsed, is_match_host=False, account_id=7, connection_id=0x1234
        )
        reparsed = parse_connect_c0(changed)
        self.assertEqual(reparsed.connection_id, 0x1234)
        self.assertEqual(reparsed.cookie, parsed.cookie)
        for invalid in (0, 0x10000):
            with self.assertRaises(ValueError):
                make_authorized_local_c0(
                    original, parsed, is_match_host=False, account_id=7, connection_id=invalid
                )

    def test_authorization_requires_unique_typed_decision_and_matching_cookie(self):
        response = b's:6:"cookie";s:6:"cookie";s:10:"account_id";i:2;s:11:"game_cookie";s:4:"abcd";'
        for decision in (0, 1):
            wire = response + f's:13:"is_match_host";i:{decision};'.encode()
            ok, _, creator, account_id = validate_c_conn_response(wire, "cookie")
            self.assertTrue(ok)
            self.assertEqual(creator, bool(decision))
            self.assertEqual(account_id, 2)
            self.assertFalse(validate_c_conn_response(wire, "wrong-cookie")[0])
        for suffix in (b"", b's:13:"is_match_host";s:1:"1";', b's:13:"is_match_host";i:2;',
                       b's:13:"is_match_host";i:0;s:13:"is_match_host";i:1;'):
            result = validate_c_conn_response(response + suffix, "cookie")
            self.assertEqual((result[0], result[2], result[3]), (False, False, 0))

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
                    approved, _, decision, account_id = authorize_connect_c0(parsed, "http://localhost", 1)
                self.assertTrue(approved)
                self.assertEqual(decision, creator)
                rewritten = make_authorized_local_c0(
                    raw, parsed, is_match_host=decision, account_id=account_id
                )
                self.assertEqual(rewritten[parsed.flag_offset] & 1, int(creator))
                self.assertEqual(
                    struct.unpack_from("<I", rewritten, parsed.account_id_offset)[0],
                    0x80000000 | account,
                )
                self.assertEqual(state["pending_host_account_id"], 1)

    def test_gateway_marks_only_an_authenticated_reconnect(self):
        original = connection("", marker=0xFF)
        parsed = parse_connect_c0(original)
        fresh = make_authorized_local_c0(
            original, parsed, is_match_host=False, is_reconnect=False, account_id=7
        )
        returning = make_authorized_local_c0(
            original, parsed, is_match_host=False, is_reconnect=True, account_id=7
        )
        self.assertEqual(fresh[parsed.flag_offset] & 3, 0)
        self.assertEqual(returning[parsed.flag_offset] & 3, 2)
