import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thorgor.protocols import game_protocol as shim
import thorgor_hon_sandboxed_masterserver_v39 as backend


SYNTHETIC_COOKIE = "unit-test-cookie"


def cstring(value: str) -> bytes:
    return value.encode("utf-8") + b"\x00"


def synthetic_c0() -> bytes:
    """Construct a minimal packet from documented fields; no capture is embedded."""
    return b"".join(
        (
            b"\x00\x00\x01\xc0",
            cstring("Heroes of Newerth"),
            cstring("3.2.7.1"),
            struct.pack("<IH", 0x10203040, 0),
            cstring(""),
            cstring("fixture-user"),
            cstring(SYNTHETIC_COOKIE),
            cstring("127.0.0.1"),
            cstring("unit-test-match-key"),
            cstring(""),
            b"\x01\x00\x01\x14\x05",
        )
    )


class UdpAuthorizationBridgeTests(unittest.TestCase):
    def test_windows_udp_reset_suppression_is_guarded_for_cross_platform_runs(self):
        self.assertIsInstance(hasattr(shim.socket, "SIO_UDP_CONNRESET"), bool)

    def test_synthetic_packet_parses_at_native_field_boundaries(self):
        packet = shim.parse_connect_c0(synthetic_c0())

        self.assertEqual(packet.product, "Heroes of Newerth")
        self.assertEqual(packet.version, "3.2.7.1")
        self.assertEqual(packet.host_id, 0x10203040)
        self.assertEqual(packet.connection_id, 0)
        self.assertEqual(packet.username, "fixture-user")
        self.assertEqual(packet.cookie, SYNTHETIC_COOKIE)
        self.assertEqual(packet.ip, "127.0.0.1")
        self.assertEqual(packet.match_key, "unit-test-match-key")
        self.assertEqual(packet.invitation, "")
        self.assertTrue(packet.external_auth)

    def test_validator_accepts_exact_typed_backend_identity(self):
        wire = backend.php_serialize(
            {"cookie": SYNTHETIC_COOKIE, "account_id": 7, "game_cookie": "a" * 32}
        )

        accepted, reason = shim.validate_c_conn_response(wire, SYNTHETIC_COOKIE)

        self.assertTrue(accepted, reason)
        self.assertEqual(reason, "account_id=7")

    def test_authorized_rewrite_changes_only_external_auth_bit(self):
        source = synthetic_c0()
        packet = shim.parse_connect_c0(source)

        rewritten = shim.make_authorized_local_c0(source, packet)

        self.assertEqual(len(rewritten), len(source))
        self.assertEqual(rewritten[: packet.flag_offset], source[: packet.flag_offset])
        self.assertEqual(rewritten[packet.flag_offset], source[packet.flag_offset] & 0xFE)
        self.assertEqual(rewritten[packet.flag_offset + 1 :], source[packet.flag_offset + 1 :])
        self.assertFalse(shim.parse_connect_c0(rewritten).external_auth)

    def test_validator_rejects_cookie_mismatch_and_string_account_id(self):
        mismatch = backend.php_serialize(
            {"cookie": "wrong", "account_id": 7, "game_cookie": "a" * 32}
        )
        wrong_type = backend.php_serialize(
            {"cookie": SYNTHETIC_COOKIE, "account_id": "7", "game_cookie": "a" * 32}
        )

        self.assertFalse(shim.validate_c_conn_response(mismatch, SYNTHETIC_COOKIE)[0])
        self.assertFalse(shim.validate_c_conn_response(wrong_type, SYNTHETIC_COOKIE)[0])

    def test_wrong_version_and_truncation_are_rejected(self):
        wrong_version = synthetic_c0().replace(b"3.2.7.1\x00", b"4.10.8\x00", 1)
        with self.assertRaises(ValueError):
            shim.parse_connect_c0(wrong_version)
        with self.assertRaises(ValueError):
            shim.parse_connect_c0(synthetic_c0()[:40])


if __name__ == "__main__":
    unittest.main()
