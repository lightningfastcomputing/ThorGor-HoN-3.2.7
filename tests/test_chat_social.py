import struct
import tempfile
import unittest
from pathlib import Path

from thorgor.chat.protocol import encode_player_count
from thorgor.chat.social import (
    FRIEND_APPROVE_RESPONSE,
    FRIEND_REQUEST_RESPONSE,
    SocialService,
)
from thorgor.master.accounts import AccountStore


class ChatSocialTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = AccountStore(Path(self.tempdir.name) / "accounts.db")
        self.requester = self.store.add_or_update("pwnrbwnr", "secret")
        self.target = self.store.add_or_update("player", "secret")
        self.online = {self.requester.account_id, self.target.account_id}
        self.sent = []

        def send(account_id, command, payload):
            if account_id not in self.online:
                return False
            self.sent.append((account_id, command, payload))
            return True

        self.social = SocialService(
            self.store, send, lambda account_id: account_id in self.online,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_friend_request_is_persisted_and_delivered_to_both_players(self):
        self.assertTrue(self.social.request(self.requester.account_id, "player"))

        requester_packet, target_packet = self.sent
        self.assertEqual(requester_packet[:2],
                         (self.requester.account_id, FRIEND_REQUEST_RESPONSE))
        self.assertEqual(requester_packet[2][0], 1)
        self.assertEqual(target_packet[:2],
                         (self.target.account_id, FRIEND_REQUEST_RESPONSE))
        self.assertEqual(target_packet[2][0], 2)
        self.assertIn(b"pwnrbwnr\0", target_packet[2])
        name_end = target_packet[2].index(b"\0", 5)
        connection_status_offset = name_end + 1 + 4
        self.assertEqual(target_packet[2][connection_status_offset], 3)
        with self.store.lock, self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM friend_requests").fetchone()[0], 1)

    def test_offline_request_is_delivered_after_target_connects(self):
        self.online.remove(self.target.account_id)
        self.assertTrue(self.social.request(self.requester.account_id, "player"))
        self.assertFalse(any(packet[0] == self.target.account_id for packet in self.sent))

        self.online.add(self.target.account_id)
        self.social.deliver_pending(self.target.account_id)
        target_packet = self.sent[-1]
        self.assertEqual(target_packet[:2],
                         (self.target.account_id, FRIEND_REQUEST_RESPONSE))
        self.assertEqual(target_packet[2][0], 2)

    def test_approval_creates_bidirectional_friendship(self):
        self.social.request(self.requester.account_id, "player")
        self.sent.clear()

        self.assertTrue(self.social.approve(self.target.account_id, "pwnrbwnr"))

        self.assertEqual({packet[0] for packet in self.sent},
                         {self.requester.account_id, self.target.account_id})
        self.assertTrue(all(packet[1] == FRIEND_APPROVE_RESPONSE for packet in self.sent))
        with self.store.lock, self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM friend_requests").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM friends").fetchone()[0], 2)

    def test_player_count_payload_matches_protocol_47(self):
        self.assertEqual(encode_player_count(2), struct.pack("<I", 2) + b"\0")
        with self.assertRaises(ValueError):
            encode_player_count(-1)


if __name__ == "__main__":
    unittest.main()
