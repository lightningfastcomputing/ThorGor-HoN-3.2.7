import struct
import time
import unittest

from thorgor.chat.protocol import cstr
from thorgor.matchmaking.chat_gateway import MatchmakingChatGateway
from thorgor.matchmaking.endpoint import MatchmakingEndpoint
from thorgor.protocols import matchmaking_protocol as wire


def create_payload(group_type=3, game_type=2, modes="botmatch"):
    return (
        cstr("3.2.7.1") + bytes((group_type, game_type)) + cstr("caldavar")
        + cstr(modes) + cstr("USE") + bytes((0, 1, 2, 1))
    )


class MatchmakingChatGatewayTests(unittest.TestCase):
    def setUp(self):
        self.next_match = 70
        self.state = {"native_start_game_injected_for": 0}
        self.sent = {1: [], 2: []}

        def allocate(_candidate, _mode, account_ids):
            self.next_match += 1
            self.state["native_start_game_injected_for"] = self.next_match
            return self.next_match, "1", "192.168.1.154", 11236

        self.endpoint = MatchmakingEndpoint(None, allocate)
        self.gateway = MatchmakingChatGateway(self.endpoint, lambda: dict(self.state))
        for account_id in self.sent:
            self.gateway.bind(
                account_id, f"Player{account_id}",
                lambda command, payload, target=account_id: self.sent[target].append((command, payload)),
            )

    def wait_for(self, account_id, command):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if any(candidate == command for candidate, _ in self.sent[account_id]):
                return
            time.sleep(0.01)
        self.fail(f"command 0x{command:04X} was not sent to account {account_id}")

    def test_solo_coop_runs_full_queue_and_auto_connect_sequence(self):
        self.gateway.process(1, wire.TMM_GROUP_CREATE, create_payload())
        self.gateway.process(1, wire.TMM_PLAYER_READY, b"\x01\x02")
        self.gateway.process(1, wire.TMM_PLAYER_LOADING, b"\x64")
        self.wait_for(1, wire.AUTO_MATCH_CONNECT)

        commands = [command for command, _ in self.sent[1]]
        self.assertEqual(commands[0], wire.TMM_GROUP_UPDATE)
        self.assertIn(wire.TMM_START_LOADING, commands)
        self.assertIn(wire.TMM_ENTERED_QUEUE, commands)
        self.assertIn(wire.TMM_MATCH_FOUND, commands)
        self.assertIn(wire.TMM_QUEUE_UPDATE, commands)
        connect = next(payload for command, payload in self.sent[1]
                       if command == wire.AUTO_MATCH_CONNECT)
        self.assertEqual(connect[0], 5)
        self.assertEqual(struct.unpack_from("<I", connect, 1)[0], 71)
        self.assertIn(b"192.168.1.154\0", connect)

    def test_two_pvp_clients_are_assigned_together(self):
        for account_id in (1, 2):
            self.gateway.process(
                account_id, wire.TMM_GROUP_CREATE,
                create_payload(group_type=2, game_type=1, modes="ap"),
            )
            self.gateway.process(account_id, wire.TMM_PLAYER_READY, b"\x01\x01")
            self.gateway.process(account_id, wire.TMM_PLAYER_LOADING, b"\x64")

        self.wait_for(1, wire.AUTO_MATCH_CONNECT)
        self.wait_for(2, wire.AUTO_MATCH_CONNECT)
        first = self.endpoint.assignment_for(1)
        second = self.endpoint.assignment_for(2)
        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        self.assertEqual(first.account_ids, (1, 2))

    def test_group_create_decoder_rejects_truncated_payload(self):
        with self.assertRaises(ValueError):
            wire.GroupRequest.decode(cstr("3.2.7.1") + b"\x03")


if __name__ == "__main__":
    unittest.main()
