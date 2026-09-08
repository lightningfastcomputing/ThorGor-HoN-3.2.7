import unittest
from types import SimpleNamespace

from thorgor.protocols.game_protocol import (
    browser_player_count,
    browser_team_size,
    connected_player_count,
    is_client_disconnect,
    reserve_loopback_source,
)


def player(cookie: str):
    return SimpleNamespace(cookie=cookie)


class BrowserOccupancyTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
