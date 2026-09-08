import unittest

from thorgor.protocols.game_protocol import (
    make_visible_team_chat_packet,
    make_joiner_team_chat_visible,
    parse_client_team_chat,
    parse_client_team_selection,
    parse_server_team_chat,
    remember_reliable_sequence,
    rewrite_reliable_sequence,
    team_chat_recipient_routes,
)


def reliable(payload: bytes, sequence: int = 9) -> bytes:
    return b"\x00\x00\x03" + sequence.to_bytes(4, "little") + payload


class TeamChatVisibilityTests(unittest.TestCase):
    def test_parses_exact_client_team_chat(self):
        self.assertEqual(parse_client_team_chat(reliable(b"\xc8\x5chello\x00\x01")), b"hello")
        self.assertIsNone(parse_client_team_chat(reliable(b"\xc8\x5chello\x00\x00")))

    def test_parses_exact_server_team_chat(self):
        self.assertEqual(parse_server_team_chat(reliable(b"\x5f\x03\x01hello\x00")), (1, b"hello"))
        self.assertIsNone(parse_server_team_chat(reliable(b"\x5f\x04\x01hello\x00")))

    def test_parses_team_and_slot_from_observed_lobby_selection(self):
        self.assertEqual(
            parse_client_team_selection(reliable(b"\xc8\x01\x02\x00\x00\x00\x00\x00\x00\x00")),
            (2, 0),
        )
        self.assertIsNone(
            parse_client_team_selection(reliable(b"\xc8\x01\x02\x00\x00\x00\x05\x00\x00\x00"))
        )

    def test_team_chat_recipients_never_cross_team_boundary(self):
        host = ("127.0.0.1", 1000)
        joiner_one = ("127.0.0.1", 1001)
        joiner_two = ("127.0.0.1", 1002)
        teams = {host: 1, joiner_one: 2, joiner_two: 2}
        self.assertEqual(
            team_chat_recipient_routes(host, teams, (host, joiner_one, joiner_two)),
            (host,),
        )
        self.assertEqual(
            team_chat_recipient_routes(joiner_one, teams, (host, joiner_one, joiner_two)),
            (joiner_one, joiner_two),
        )

    def test_unknown_team_routes_to_nobody(self):
        sender = ("127.0.0.1", 1001)
        self.assertEqual(team_chat_recipient_routes(sender, {}, (sender,)), ())

    def test_retransmitted_team_chat_is_mirrored_only_once(self):
        observed = {}
        self.assertTrue(remember_reliable_sequence(observed, 0x373, 100.0))
        self.assertFalse(remember_reliable_sequence(observed, 0x373, 100.5))
        self.assertTrue(remember_reliable_sequence(observed, 0x374, 100.5))
        self.assertTrue(remember_reliable_sequence(observed, 0x373, 131.0))

    def test_rejects_embedded_nul_and_non_chat_packets(self):
        self.assertIsNone(make_joiner_team_chat_visible(reliable(b"\x5f\x03\x01a\x00b\x00")))
        self.assertIsNone(make_joiner_team_chat_visible(b"\x00\x00\x01\xc9"))

    def test_rewrites_native_joiner_event_for_ui_team_routing(self):
        source = reliable(b"\x5f\x03\x01hello\x00", sequence=0x12345678)
        result = make_joiner_team_chat_visible(source)
        self.assertEqual(result[:7], source[:7])
        self.assertEqual(result[7:], b"\x5f\x02\x01[THORGOR_TEAM]hello\x00")

    def test_builds_mirrored_chat_for_a_joiners_reliable_stream(self):
        packet = make_visible_team_chat_packet(0x12345678, 1, b"hello")
        self.assertEqual(packet[:7], bytes.fromhex("00000378563412"))
        self.assertEqual(packet[7:], b"\x5f\x02\x01[THORGOR_TEAM]hello\x00")

    def test_authenticated_sender_name_is_carried_without_trusting_entity_number(self):
        packet = make_visible_team_chat_packet(
            0x12345678, 0, b"hello", sender_name="Pl\u00e4yer Two"
        )
        self.assertEqual(packet[:7], bytes.fromhex("00000378563412"))
        self.assertEqual(
            packet[7:],
            b"\x5f\x02\x00[THORGOR_TEAM:506CC3A47965722054776F]hello\x00",
        )

    def test_rewrites_data_and_ack_sequences(self):
        source = reliable(b"payload", sequence=3)
        self.assertEqual(rewrite_reliable_sequence(source, 9), reliable(b"payload", sequence=9))
        ack = b"\x00\x00\x05" + (9).to_bytes(4, "little")
        self.assertEqual(rewrite_reliable_sequence(ack, 3), b"\x00\x00\x05\x03\x00\x00\x00")


if __name__ == "__main__":
    unittest.main()
