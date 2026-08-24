import importlib.util
import sys
import unittest
from pathlib import Path

from thorgor.chat import server as migrated


ROOT = Path(__file__).resolve().parents[1]
LEGACY_PATH = ROOT / "chat-server" / "thorgor_hon_chatserver_v13.py"


def load_reference():
    spec = importlib.util.spec_from_file_location("chat_reference", LEGACY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reference = load_reference()


class ChatMigrationParityTests(unittest.TestCase):
    def test_command_ids_are_unchanged(self):
        names = (
            "HON_CS_AUTH_INFO",
            "HON_SC_AUTH_ACCEPTED",
            "HON_SC_PING",
            "HON_CS_PONG",
            "HON_CS_CHANNEL_MSG",
            "HON_CS_WHISPER",
            "HON_CS_JOIN_CHANNEL",
            "HON_CS_LEAVE_CHANNEL",
        )
        for name in names:
            self.assertEqual(getattr(migrated, name), getattr(reference, name), name)

    def test_packet_encoding_is_byte_identical(self):
        fixtures = (
            (0x1C00, b""),
            (0x2A00, b"\x01\x02\x03\x04"),
            (0x03, b"General\0hello world\0"),
            (0x1E, b"General\0"),
        )
        for command, payload in fixtures:
            self.assertEqual(
                migrated.encode_packet(command, payload),
                reference.encode_packet(command, payload),
            )

    def test_packet_extraction_is_structurally_identical(self):
        wire = reference.encode_packet(0x03, b"General\0hello\0")
        for data in (b"", wire[:1], wire[:-1], wire, wire + b"tail"):
            self.assertEqual(migrated.extract_packet(data), reference.extract_packet(data))

    def test_string_helpers_and_auth_derivation_are_identical(self):
        self.assertEqual(migrated.cstr("Grüße"), reference.cstr("Grüße"))
        payload = b"alpha\0omega\0"
        self.assertEqual(migrated.read_cstr(payload, 0), reference.read_cstr(payload, 0))
        account_migrated = migrated.AccountRecord(7, "player", "Player", True)
        account_reference = reference.AccountRecord(7, "player", "Player", True)
        self.assertEqual(migrated.expected_cookie(account_migrated), reference.expected_cookie(account_reference))
        self.assertEqual(migrated.expected_auth_hash(account_migrated), reference.expected_auth_hash(account_reference))


if __name__ == "__main__":
    unittest.main()
