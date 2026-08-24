import unittest

from thorgor.chat.channels import ChannelDirectory
from thorgor.chat.protocol import encode_packet, extract_packet
from thorgor.game_manager.match_lifecycle import MatchLifecycle, MatchPhase
from thorgor.game_manager.server_registry import DedicatedServer, ServerRegistry, ServerState
from thorgor.matchmaking.matchmaker import Matchmaker
from thorgor.matchmaking.queue import MatchQueue, MatchRequest


class ChatBoundaryTests(unittest.TestCase):
    def test_chat_packet_round_trip_and_partial_buffer(self):
        wire = encode_packet(0x1E, b"General\0")
        self.assertIsNone(extract_packet(wire[:-1]))
        total, command, payload, raw = extract_packet(wire + b"tail")
        self.assertEqual((total, command, payload, raw), (len(wire), 0x1E, b"General\0", wire))

    def test_channel_members_are_case_insensitive_and_deterministic(self):
        channels = ChannelDirectory()
        channels.join("General", "Zulu")
        channels.join("general", "alpha")
        self.assertEqual(channels.members("GENERAL"), ("alpha", "Zulu"))
        self.assertEqual(channels.leave("general", "alpha"), ("Zulu",))


class MatchmakingBoundaryTests(unittest.TestCase):
    def test_two_player_fifo_match_uses_one_assignment(self):
        queue = MatchQueue()
        queue.join(MatchRequest(10, "A"))
        queue.join(MatchRequest(20, "B"))
        queue.join(MatchRequest(30, "C"))
        matchmaker = Matchmaker(queue, lambda match_id, mode, ids: ("slave-1", "10.0.0.1", 11235))
        assignment = matchmaker.form_match()
        self.assertEqual(assignment.account_ids, (10, 20))
        self.assertEqual(queue.snapshot()[0].account_id, 30)

    def test_duplicate_account_is_rejected(self):
        queue = MatchQueue()
        self.assertTrue(queue.join(MatchRequest(10, "A")))
        self.assertFalse(queue.join(MatchRequest(10, "A again")))

    def test_failed_allocation_restores_requests(self):
        queue = MatchQueue()
        queue.join(MatchRequest(10, "A"))
        queue.join(MatchRequest(20, "B"))
        def fail(*_):
            raise RuntimeError("no slave")
        with self.assertRaises(RuntimeError):
            Matchmaker(queue, fail).form_match()
        self.assertEqual(tuple(r.account_id for r in queue.snapshot()), (10, 20))


class GameManagerBoundaryTests(unittest.TestCase):
    def test_registry_allocates_only_idle_servers(self):
        registry = ServerRegistry()
        registry.register(DedicatedServer("b", "10.0.0.2", 11235, ServerState.IDLE))
        registry.register(DedicatedServer("a", "10.0.0.1", 11235, ServerState.IDLE))
        selected = registry.allocate(42)
        self.assertEqual(selected.server_id, "a")
        self.assertEqual(selected.match_id, 42)
        self.assertEqual(selected.state, ServerState.ALLOCATED)

    def test_lifecycle_rejects_skipped_phase(self):
        lifecycle = MatchLifecycle(42)
        with self.assertRaises(ValueError):
            lifecycle.transition(MatchPhase.PLAYING)
        lifecycle = lifecycle.transition(MatchPhase.ALLOCATED).transition(MatchPhase.LOBBY)
        self.assertEqual(lifecycle.phase, MatchPhase.LOBBY)


if __name__ == "__main__":
    unittest.main()
