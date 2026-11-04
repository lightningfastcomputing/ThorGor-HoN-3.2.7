import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import zlib

from thorgor.protocols.native_snapshot import MAX_SNAPSHOT, SnapshotReceiver
from thorgor.tools.harness_clients import Identity, NativeClient
from thorgor.tools.harness_gameplay import (
    classify_departure, creator_departure, verify_baseline, verify_continuity,
)


class SnapshotTests(unittest.TestCase):
    def test_complete_plain_and_compressed_envelopes(self):
        body = struct.pack("<I", 123) + b"native-state"
        plain = b"\x5a" + struct.pack("<I", len(body)) + body
        packed = zlib.compress(body)
        compressed = b"\x5b" + struct.pack("<II", len(packed), len(body)) + packed
        self.assertEqual(SnapshotReceiver().receive(plain), 123)
        self.assertEqual(SnapshotReceiver().receive(compressed), 123)

    def test_compressed_fragments_require_all_parts_and_matching_frame(self):
        body = struct.pack("<I", 456) + b"native-state" * 20
        packed = zlib.compress(body)
        first = b"\x5c" + struct.pack("<IB", 456, 0) + packed[:5]
        last = b"\x5e" + struct.pack("<IBIH", 456, 1, len(body), len(packed) - 5) + packed[5:]
        receiver = SnapshotReceiver()
        self.assertIsNone(receiver.receive(last))
        self.assertIsNone(receiver.receive(last))
        self.assertEqual(receiver.receive(first), 456)
        mismatched = b"\x5d" + struct.pack("<IBH", 999, 0, len(body)) + body
        with self.assertRaises(ValueError):
            SnapshotReceiver().receive(mismatched)

    def test_rejects_truncation_conflicts_and_oversized_data(self):
        receiver = SnapshotReceiver()
        with self.assertRaises(ValueError):
            receiver.receive(b"\x5a" + struct.pack("<I", 30) + b"short")
        with self.assertRaises(ValueError):
            receiver.receive(b"\x5b" + struct.pack("<II", 1, MAX_SNAPSHOT + 1) + b"x")
        receiver.receive(b"\x5c" + struct.pack("<IB", 1, 0) + b"one")
        with self.assertRaises(ValueError):
            receiver.receive(b"\x5c" + struct.pack("<IB", 1, 0) + b"two")

    def test_corrupt_or_truncated_zlib_stream_is_rejected(self):
        body = struct.pack("<I", 7) + b"state"
        packed = zlib.compress(body)[:-2]
        packet = b"\x5b" + struct.pack("<II", len(packed), len(body)) + packed
        with self.assertRaises(ValueError):
            SnapshotReceiver().receive(packet)


class ClientTelemetryTests(unittest.TestCase):
    def test_duplicate_frames_and_acknowledgments_are_independent_per_client(self):
        with patch("thorgor.tools.harness_clients.socket.socket"):
            first = NativeClient("one", Identity(1, "cookie-one", "a" * 40), "key")
            second = NativeClient("two", Identity(2, "cookie-two", "b" * 40), "")
            try:
                body = struct.pack("<I", 12) + b"state"
                packet = b"\0\0\1\x5a" + struct.pack("<I", len(body)) + body
                first.receive(packet)
                first.receive(packet)
                second.receive(packet)
                self.assertEqual(first.snapshot_frames, 1)
                self.assertEqual(first.snapshot_complete, 2)
                self.assertEqual(second.snapshot_frames, 1)
                seq = first.game_command(0x2F)
                self.assertIn(seq, first.pending)
                first.receive(b"\0\0\5" + struct.pack("<I", seq))
                self.assertNotIn(seq, first.pending)
                self.assertEqual(second.next_sequence, 1)
            finally:
                first.close()
                second.close()


class DepartureOracleTests(unittest.TestCase):
    def test_expected_bug_mode_cannot_hide_failure_of_a_repair(self):
        from thorgor.tools.harness import run
        with self.assertRaisesRegex(ValueError, "requires frozen v39"):
            run("native-match", disconnect_creator=True, native_variant="registry-continuity",
                expect_freeze=True)

    def samples(self, frames, **overrides):
        return [{"clients": [{"snapshot_frames": count, "snapshot_errors": 0,
                              "snapshot_packets": count, "snapshot_complete": count,
                              "sent": 20, **overrides}]} for count in frames]

    def test_frozen_and_continuing_streams(self):
        self.assertEqual(classify_departure(self.samples([0, 0, 0])), "reproduced_freeze")
        self.assertEqual(classify_departure(self.samples([20, 20, 20])), "continued_state")

    def test_decode_failures_partial_fragments_and_stopped_input_are_inconclusive(self):
        for samples in (
            self.samples([0, 0, 0], snapshot_errors=1),
            self.samples([0, 0, 0], snapshot_packets=5),
            self.samples([0, 0, 0], sent=0),
            self.samples([0, 20, 0]),
            [],
        ):
            with self.subTest(samples=samples):
                self.assertEqual(classify_departure(samples), "inconclusive")

    def test_departure_preserves_active_joiner_without_admission_transition_bit(self):
        creator = SimpleNamespace(account_id=1, disconnect=Mock())
        joiner = SimpleNamespace(account_id=2, socket=Mock())
        joiner.socket.getsockname.return_value = ("127.0.0.1", 12345)
        state = {"players": [{"account_id_low30": 2, "native_client_number": 1,
                              "connection_status": 0x22, "player": "0x10000", "team": 2,
                              "hero_index": 4227, "selected_hero": 1407}],
                 "native_match_id": 1, "phase": 6, "engine_time": 1000}
        samples = self.samples([20] * 15)
        for number, sample in enumerate(samples, 1):
            sample.update(native_transport=None, native_state={**state, "engine_time": 1000 + 1000 * number})
        with patch("thorgor.tools.harness_gameplay.inspect_gameplay", return_value=state), \
                patch("thorgor.tools.harness_gameplay.wait_state"), \
                patch("thorgor.tools.harness_gameplay.observe_state",
                      return_value=samples):
            creator_departure(123, [creator, joiner], Mock(), lambda name, fn: fn(), Mock())
            creator.disconnect.assert_called_once_with()
            state["players"][0]["connection_status"] |= 1
            with self.assertRaisesRegex(RuntimeError, "joiner native connection changed"):
                creator_departure(123, [creator, joiner], Mock(), lambda name, fn: fn(), Mock())

    def test_baseline_requires_both_clients_in_each_observation(self):
        good = [{"clients": [{"snapshot_frames": 20}, {"snapshot_frames": 19}]}] * 3
        verify_baseline(good)
        for bad in ([], good[:2], self.samples([20, 20, 20]),
                    good[:2] + [{"clients": [{"snapshot_frames": 20}, {"snapshot_frames": 0}]}]):
            with self.subTest(samples=bad), self.assertRaises(RuntimeError):
                verify_baseline(bad)

    def test_fifteen_second_gate_rejects_a_gap_even_when_final_windows_continue(self):
        player = {"account_id_low30": 2, "native_client_number": 1, "connection_status": 0x22,
                  "player": "0x10000", "team": 2, "hero_index": 4227, "selected_hero": 1407}
        before = {"players": [player], "native_match_id": 1, "phase": 6, "engine_time": 1000}
        samples = self.samples([20] * 15)
        for number, sample in enumerate(samples, 1):
            sample.update(native_transport=None, native_state={**before, "engine_time": 1000 + 1000 * number})
        verify_continuity(samples, before, 2)
        samples[1]["clients"][0]["snapshot_frames"] = 0
        self.assertEqual(classify_departure(samples), "continued_state")
        with self.assertRaisesRegex(RuntimeError, "every observation"):
            verify_continuity(samples, before, 2)
        samples[1]["clients"][0]["snapshot_frames"] = 20
        samples[2]["native_state"] = {**before, "engine_time": 4000, "native_match_id": 2}
        with self.assertRaisesRegex(RuntimeError, "identity/clock"):
            verify_continuity(samples, before, 2)
