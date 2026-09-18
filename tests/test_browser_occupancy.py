import unittest
import struct
from types import SimpleNamespace

from thorgor.protocols.game_protocol import (
    browser_player_count,
    browser_team_size,
    connected_player_count,
    is_client_disconnect,
    local_account_id_from_cookie,
    make_reconnect_info_reply,
    parse_reconnect_info_request,
    parse_server_client_assignment,
    reconnect_number_for_admission,
    reserve_loopback_source,
    reserve_identity_source,
)


def player(cookie: str):
    return SimpleNamespace(cookie=cookie)


class BrowserOccupancyTests(unittest.TestCase):
    def test_native_client_number_is_parsed_for_diagnostics(self):
        packet = (
            b"\0\0\3"
            + struct.pack("<I", 9)
            + b"\x50\0\0"
            + struct.pack("<I", 7)
            + b"\0"
        )
        self.assertEqual(parse_server_client_assignment(packet), 7)
        self.assertEqual(parse_server_client_assignment(packet[:7] + b"\x69\x01" + packet[7:]), 7)
        host = packet[:10] + struct.pack("<I", 0) + packet[14:]
        self.assertEqual(parse_server_client_assignment(host[:7] + b"\x69\x01" + host[7:]), 0)
        for malformed in (
            b"",
            packet[:7] + b"\x51" + packet[8:],
            packet[:10] + struct.pack("<I", 256) + b"\0",
            packet[:7] + b"\x69\x00" + packet[7:],
            packet[:7] + b"\x51arbitrary" + packet[7:],
            packet[:7] + b"\x69\x01" + packet[7:12],
        ):
            self.assertIsNone(parse_server_client_assignment(malformed))

    def test_reconnect_c0_retry_keeps_identity_after_old_route_is_released(self):
        first = reconnect_number_for_admission("leaver", None, retired=True, native_number=1)
        retry = reconnect_number_for_admission("leaver", ("leaver", first), retired=False, native_number=1)
        self.assertEqual((first, retry), (1, 1))
        self.assertIsNone(reconnect_number_for_admission("other", ("leaver", first), retired=False, native_number=1))
        self.assertIsNone(reconnect_number_for_admission("host", ("host", None), retired=False, native_number=0))
        self.assertEqual(reconnect_number_for_admission("host", ("host", None), retired=True, native_number=0), 0)
        for number in (None, -1, 128):
            with self.assertRaises(ValueError):
                reconnect_number_for_admission("leaver", None, retired=True, native_number=number)
    def test_live_lobby_tracks_authenticated_players(self):
        for count in range(1, 11):
            connections = [player(f"cookie-{index}") for index in range(count)]
            self.assertEqual(browser_player_count(connections, True, 1, 10), count)

    def test_reconnect_does_not_double_count_same_identity(self):
        connections = [player("host"), player("joiner"), player("joiner")]
        self.assertEqual(connected_player_count(connections), 2)
        self.assertEqual(browser_player_count(connections, True, 1, 10), 2)

    def test_live_lobby_has_creator_fallback_and_clamps_to_capacity(self):
        self.assertEqual(browser_player_count([], True, 1, 10), 1)
        self.assertEqual(
            browser_player_count([player(str(index)) for index in range(12)], True, 1, 10),
            10,
        )

    def test_idle_reply_retains_configured_count(self):
        self.assertEqual(browser_player_count([player("ignored")], False, 1, 10), 1)

    def test_browser_team_size_comes_from_active_lobby_options(self):
        for size in range(1, 6):
            state = {"match_options": f"map:caldavar teamsize:{size} mode:normal "}
            self.assertEqual(browser_team_size(state, True, 0, 10), size)

    def test_browser_team_size_prefers_explicit_state_and_has_5v5_fallback(self):
        self.assertEqual(browser_team_size({"match_team_size": 3}, True, 0, 10), 3)
        self.assertEqual(browser_team_size({}, True, 0, 10), 5)
        self.assertEqual(browser_team_size({}, False, 0, 10), 0)

    def test_invalid_team_size_does_not_escape_wire_bounds(self):
        self.assertEqual(
            browser_team_size({"match_options": "teamsize:99 "}, True, 0, 10),
            5,
        )

    def test_only_exact_c3_datagram_retires_lobby_route(self):
        self.assertTrue(is_client_disconnect(b"\x00\x00\x01\xc3"))
        for packet in (
            b"\x00\x00\x01\xc9",
            b"\x00\x00\x01\xc3\x00",
            b"\x00\x00\x03\xc3",
            b"",
        ):
            self.assertFalse(is_client_disconnect(packet))

    def test_loopback_identity_is_never_reused_during_proxy_run(self):
        allocated = set()
        first = reserve_loopback_source(allocated)
        second = reserve_loopback_source(allocated)
        self.assertEqual(first, "127.0.0.2")
        self.assertEqual(second, "127.0.0.3")
        self.assertEqual(reserve_loopback_source(allocated), "127.0.0.4")

    def test_authenticated_identity_keeps_its_proxy_source_while_active(self):
        allocated = set()
        sources = {}
        first = reserve_identity_source("player-cookie", sources, allocated)
        self.assertEqual(first, "127.0.0.2")
        self.assertEqual(
            reserve_identity_source("player-cookie", sources, allocated), first
        )
        self.assertEqual(
            reserve_identity_source("other-cookie", sources, allocated), "127.0.0.3"
        )
        self.assertEqual(reserve_identity_source(None, sources, allocated), "127.0.0.4")

    def test_reconnect_rotates_stale_native_socket_identity(self):
        allocated = set()
        sources = {}
        first = reserve_identity_source("player-cookie", sources, allocated)
        replacement = reserve_identity_source(
            "player-cookie", sources, allocated, replace=True
        )
        self.assertEqual(first, "127.0.0.2")
        self.assertEqual(replacement, "127.0.0.3")
        self.assertEqual(
            reserve_identity_source("player-cookie", sources, allocated), replacement
        )

    def test_native_reconnect_probe_is_recognized_exactly(self):
        packet = b"\x00\x00\x01\xcc" + struct.pack("<IIH", 42, 7, 0x1234)
        request = parse_reconnect_info_request(packet)
        self.assertIsNotNone(request)
        self.assertEqual((request.match_id, request.account_id, request.connection_id),
                         (42, 7, 0x1234))
        for malformed in (packet[:-1], packet + b"\0", b"\x00\x00\x01\xca" + packet[4:]):
            self.assertIsNone(parse_reconnect_info_request(malformed))

    def test_local_account_id_is_recovered_only_from_our_cookie(self):
        self.assertEqual(local_account_id_from_cookie("THORGOR_LOCAL_COOKIE_00000003"), 3)
        for cookie in ("cookie", "THORGOR_LOCAL_COOKIE_3", "THORGOR_LOCAL_COOKIE_00000000"):
            self.assertIsNone(local_account_id_from_cookie(cookie))

    def test_reconnect_reply_requires_same_live_match_and_unexpired_leaver(self):
        request = parse_reconnect_info_request(
            b"\x00\x00\x01\xcc" + struct.pack("<IIH", 42, 7, 0)
        )
        self.assertIsNotNone(request)
        reply = make_reconnect_info_reply(request, 42, {7: 130.0}, 100.0)
        self.assertEqual(reply[:4], b"\x00\x00\x01\x6f")
        self.assertEqual(struct.unpack_from("<I", reply, 4)[0], 30000)
        for denied in (
            make_reconnect_info_reply(request, 41, {7: 130.0}, 100.0),
            make_reconnect_info_reply(request, 42, {7: 99.0}, 100.0),
        ):
            self.assertEqual(denied[:4], b"\x00\x00\x01\x6f")
            self.assertEqual(struct.unpack_from("<I", denied, 4)[0], 0)


if __name__ == "__main__":
    unittest.main()
