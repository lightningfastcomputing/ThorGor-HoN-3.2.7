import unittest
import tempfile
from pathlib import Path

from thorgor.master.accounts import AccountStore
from thorgor.master.server import Session, delete_notification_response, php_serialize, success_payload


class MasterNotificationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = AccountStore(Path(self.tempdir.name) / "accounts.db")
        self.requester = self.store.add_or_update("pwnrbwnr", "secret")
        self.target = self.store.add_or_update("player", "secret")
        self.authorization = self.store.register_game_authorization(self.target.account_id)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_delete_notification_echoes_ids_and_ok_status(self):
        response = delete_notification_response({
            "notify_id": ["102355729"],
            "internal_id": ["0"],
        })

        self.assertEqual(response, {
            "notify_id": "102355729",
            "internal_id": "0",
            "status": "OK",
        })
        encoded = php_serialize(response)
        self.assertIn(b's:9:"notify_id";s:9:"102355729";', encoded)
        self.assertIn(b's:6:"status";s:2:"OK";', encoded)

    def test_delete_notification_defaults_missing_ids_to_zero(self):
        self.assertEqual(delete_notification_response({}), {
            "notify_id": "0",
            "internal_id": "0",
            "status": "OK",
        })

    def test_delete_notification_accepts_friendship_atomically(self):
        with self.store.lock, self.store.connect() as db:
            db.execute("""INSERT INTO friend_requests
                (requester_id,target_id,notification_id) VALUES (?,?,?)""",
                (self.requester.account_id, self.target.account_id, 102355729))
            db.commit()

        response = delete_notification_response({
            "cookie": [self.authorization.cookie],
            "notify_id": ["102355729"],
            "internal_id": ["2"],
        }, self.store)

        self.assertEqual(response["status"], "OK")
        self.assertEqual(
            [friend.account_id for friend in self.store.list_friends(self.target.account_id)],
            [self.requester.account_id],
        )
        self.assertEqual(
            [friend.account_id for friend in self.store.list_friends(self.requester.account_id)],
            [self.target.account_id],
        )
        self.assertEqual(self.store.pending_friend_notifications(self.target.account_id), [])

    def test_login_payload_contains_pending_notifications_and_persisted_buddies(self):
        with self.store.lock, self.store.connect() as db:
            db.execute("""INSERT INTO friend_requests
                (requester_id,target_id,notification_id) VALUES (?,?,?)""",
                (self.requester.account_id, self.target.account_id, 42))
            db.commit()
        session = Session(
            username=self.target.username, account_id=self.target.account_id,
            nickname=self.target.nickname, A=1, salt=1, salt2="", transformed_password="",
            b=1, B=1, v=1, k=1, u=1, S=1, K=b"", expected_M1=b"", M2=b"",
            created_at=0, client_ip="127.0.0.1",
        )

        pending = success_payload(session, self.authorization.cookie, self.store)
        self.assertEqual(pending["notifications"][0]["notify_id"], 42)
        self.assertIn("pwnrbwnr||23", pending["notifications"][0]["notification"])

        delete_notification_response({
            "cookie": [self.authorization.cookie], "notify_id": ["42"],
        }, self.store)
        accepted = success_payload(session, self.authorization.cookie, self.store)
        self.assertEqual(accepted["notifications"], [])
        self.assertEqual(
            accepted["buddy_list"][self.target.account_id][self.requester.account_id]["nickname"],
            "pwnrbwnr",
        )


if __name__ == "__main__":
    unittest.main()
