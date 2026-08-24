import importlib.util
import struct
import sys
import unittest
from pathlib import Path

from thorgor.protocols import game_protocol


ROOT = Path(__file__).resolve().parents[1]


def load_reference():
    name = "thorgor_udp_migration_reference"
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "thorgor" / "runtime" / "hon_udp_shim.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GameProtocolMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = load_reference()

    def test_proxy_challenge_bytes_match_reference(self):
        self.assertEqual(
            game_protocol.build_proxy_challenge(0x10203040, 0x50607080),
            self.reference.build_proxy_challenge(0x10203040, 0x50607080),
        )

    def test_lobby_create_parser_matches_reference(self):
        packet = (
            b"\x00\x00\x03\xd4\x01\x00\x00\xc4\xc8\x1a"
            b"LAN Match\x00map:caldavar teamsize:5 mode:normal casual:true \x00"
        )
        self.assertEqual(
            game_protocol.parse_lobby_create(packet),
            self.reference.parse_lobby_create(packet),
        )

    def test_connect_parser_matches_reference_field_for_field(self):
        cstr = lambda value: value.encode("utf-8") + b"\x00"
        packet = b"".join(
            (
                b"\x00\x00\x01\xc0",
                cstr("Heroes of Newerth"),
                cstr("3.2.7.1"),
                struct.pack("<IH", 17, 23),
                cstr("password"),
                cstr("player"),
                cstr("cookie"),
                cstr("127.0.0.1"),
                cstr("match-key"),
                cstr("invitation"),
                b"\x01\x00\x01\x14\x05",
            )
        )
        actual = game_protocol.parse_connect_c0(packet)
        expected = self.reference.parse_connect_c0(packet)
        self.assertEqual(actual.__dict__, expected.__dict__)

    def test_route_trace_description_matches_reference(self):
        packets = (
            b"\x00\x00\x05" + struct.pack("<I", 19),
            b"\x00\x00\x03" + struct.pack("<I", 20) + b"payload",
            b"\x00\x00\x01\xc9",
        )
        for packet in packets:
            self.assertEqual(
                game_protocol.describe_trace_datagram(packet),
                self.reference.describe_trace_datagram(packet),
            )


if __name__ == "__main__":
    unittest.main()
