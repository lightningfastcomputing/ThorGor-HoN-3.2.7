import struct
import unittest

from hon_udp_shim import (
    PICKER_STATE_PREFIX,
    describe_trace_datagram,
    extract_picker_hero_block_suffix,
    repair_truncated_picker_packet,
)


class RouteTraceV73Tests(unittest.TestCase):
    def test_reliable_data_keeps_sequence_and_full_payload(self):
        packet = b"\x00\x00\x03" + struct.pack("<I", 20) + b"\x56\x04\x00\x0f\x05payload"
        result = describe_trace_datagram(packet)
        self.assertEqual(result["kind"], "reliable_data")
        self.assertEqual(result["sequence"], 20)
        self.assertEqual(result["payload_bytes"], len(packet) - 7)
        self.assertEqual(result["hex"], packet.hex())

    def test_reliable_ack_keeps_sequence_without_payload_copy(self):
        packet = b"\x00\x00\x05" + struct.pack("<I", 19)
        result = describe_trace_datagram(packet)
        self.assertEqual(result["kind"], "reliable_ack")
        self.assertEqual(result["sequence"], 19)
        self.assertNotIn("hex", result)

    def test_control_packet_identifies_keepalive(self):
        result = describe_trace_datagram(b"\x00\x00\x01\xc9")
        self.assertEqual(result["kind"], "control")
        self.assertEqual(result["command"], 0xC9)

    def test_exact_six_block_suffix_is_validated_and_repairs_truncation(self):
        suffix = b"".join(
            b"\x60" + struct.pack("<HH", block_id, 5) + struct.pack("<HHB", block_id, 1000 + block_id, 0xFE)
            for block_id in range(3, 9)
        )
        sequence = b"\x00\x00\x03" + struct.pack("<I", 49)
        host_packet = sequence + PICKER_STATE_PREFIX + suffix
        truncated = sequence + PICKER_STATE_PREFIX
        self.assertEqual(extract_picker_hero_block_suffix(host_packet), (suffix, tuple(range(3, 9))))
        self.assertEqual(repair_truncated_picker_packet(truncated, suffix), host_packet)

    def test_repair_rejects_wrong_prefix_and_incomplete_block_set(self):
        sequence = b"\x00\x00\x03" + struct.pack("<I", 49)
        incomplete = b"\x60" + struct.pack("<HH", 3, 5) + b"\x00" * 5
        self.assertIsNone(extract_picker_hero_block_suffix(sequence + PICKER_STATE_PREFIX + incomplete))
        self.assertIsNone(repair_truncated_picker_packet(sequence + b"wrong-prefix", incomplete))


if __name__ == "__main__":
    unittest.main()
