import struct
import unittest

from thorgor.chat import presence
from thorgor.chat.protocol import cstr


class ChatPresenceTests(unittest.TestCase):
    def test_initial_status_encodes_online_friend_contract(self):
        payload = presence.initial_status([presence.Peer(2, "player")])
        self.assertEqual(struct.unpack_from("<I", payload)[0], 1)
        self.assertEqual(struct.unpack_from("<I", payload, 4)[0], 2)
        self.assertEqual(payload[8:10], bytes((3, 64)))
        self.assertTrue(payload.endswith(struct.pack("<I", 0)))

    def test_protocol_47_status_update_omits_newer_ascension_tail(self):
        online = presence.status_update(presence.Peer(2, "player"))
        offline = presence.status_update(
            presence.Peer(2, "player", status=presence.STATUS_DISCONNECTED),
        )
        self.assertEqual(len(online), 14)
        self.assertEqual(online[4:6], bytes((3, 64)))
        self.assertEqual(offline[4], 0)

    def test_instant_message_request_and_first_contact_round_trip_shape(self):
        request = presence.InstantMessageRequest.decode(cstr("player") + cstr("hello") + b"\x01")
        self.assertEqual(request.target_name, "player")
        self.assertEqual(request.message, "hello")
        self.assertTrue(request.send_client_information)

        recipient = presence.first_contact(1, presence.Peer(1, "pwnrbwnr"), "hello")
        sender = presence.first_contact(2, presence.Peer(2, "player"), "hello")
        self.assertEqual(recipient[0], 1)
        self.assertIn(cstr("pwnrbwnr"), recipient)
        self.assertEqual(sender[0], 2)
        self.assertIn(cstr("player"), sender)

    def test_subsequent_and_failed_message_shapes(self):
        self.assertEqual(
            presence.subsequent_message("pwnrbwnr", "hello"),
            b"\x00" + cstr("pwnrbwnr") + cstr("hello"),
        )
        self.assertEqual(presence.failed_message("offline"), cstr("offline"))


if __name__ == "__main__":
    unittest.main()
