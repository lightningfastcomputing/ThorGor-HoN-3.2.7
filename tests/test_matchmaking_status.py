import unittest

from thorgor.matchmaking import ClientProtocolStatus, MatchmakingService


class MatchmakingIntegrationStatusTests(unittest.TestCase):
    def test_status_reports_live_protocol_47_boundary(self):
        status = MatchmakingService.status()
        self.assertEqual(status.domain_logic, "implemented_and_tested")
        self.assertTrue(status.simulation_api)
        self.assertIs(status.live_client_protocol, ClientProtocolStatus.CHAT_PROTOCOL_47)
        self.assertIn("auto-connect", status.detail)


if __name__ == "__main__":
    unittest.main()
