import unittest

from thorgor.master.server import delete_notification_response, php_serialize


class MasterNotificationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
