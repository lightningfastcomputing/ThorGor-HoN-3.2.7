import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thorgor.game_manager import dedicated_slave as protocol


class ManagerProtocolTests(unittest.TestCase):
    def test_typed_start_game_match_id_parser(self):
        wire = b'a:1:{s:8:"match_id";i:42;}'
        self.assertEqual(protocol.parse_start_game_match_id(wire), 42)
        with self.assertRaises(ValueError):
            protocol.parse_start_game_match_id(b'a:1:{s:8:"match_id";s:2:"42";}')

    def test_typed_php_session_parser(self):
        wire = b'a:1:{s:7:"session";s:8:"deadbeef";}'
        self.assertEqual(protocol.parse_php_string_field(wire, 'session'), 'deadbeef')
        with self.assertRaises(ValueError):
            protocol.parse_php_string_field(b'a:1:{s:7:"session";s:9:"deadbeef";}', 'session')

    def test_start_game_round_trip(self):
        payload = protocol.start_game_payload(
            'Bot Auto Match',
            'map:caldavar allowduplicate:true mode:bm',
            -1,
            -1,
            'ascii-nul',
        )
        decoded = protocol.decode_start_game(payload)
        self.assertEqual(decoded['opcode'], '0x26')
        self.assertEqual(decoded['title'], 'Bot Auto Match')
        self.assertEqual(decoded['options'], 'map:caldavar allowduplicate:true mode:bm')
        self.assertEqual((decoded['int1'], decoded['int2']), (-1, -1))
        self.assertEqual(decoded['trailing_hex'], '')

    def test_frame_is_u16_little_endian_length(self):
        payload = b'\x21'
        self.assertEqual(protocol.framed(payload), b'\x01\x00\x21')

    def test_status_payload_is_exactly_40_bytes(self):
        payload = protocol.status_payload(protocol.STATUS_IDLE)
        self.assertEqual(len(payload), 40)
        self.assertEqual(payload[:2], b'\x42\x01')
        self.assertEqual(struct.unpack_from('<H', protocol.framed(payload), 0)[0], 40)

    def test_result_decoder_preserves_unknown_tail(self):
        decoded = protocol.decode_result(b'\x46\x00ok\x00\xAA\xBB', 0x46)
        self.assertEqual(decoded['status'], 0)
        self.assertEqual(decoded['message_candidate'], 'ok')
        self.assertEqual(decoded['after_message_hex'], 'aabb')

    def test_truncated_start_game_is_rejected(self):
        with self.assertRaises(ValueError):
            protocol.decode_start_game(b'\x26name\x00options\x00\xFF')


if __name__ == '__main__':
    unittest.main()
