import unittest

from thorgor.matchmaking import ClientProtocolStatus, MatchmakingService


class MatchmakingIntegrationStatusTests(unittest.TestCase):
    def test_status_distinguishes_real_master_endpoint_from_unverified_native_commands(self):
        status = MatchmakingService.status()
        self.assertEqual(status.domain_logic, "implemented_and_tested")
        self.assertTrue(status.simulation_api)
        self.assertIs(status.live_client_protocol, ClientProtocolStatus.MASTER_ENDPOINT)
        self.assertIn("remain unverified", status.detail)


if __name__ == "__main__":
    unittest.main()
