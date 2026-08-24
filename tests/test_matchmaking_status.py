import unittest

from thorgor.matchmaking import ClientProtocolStatus, MatchmakingService


class MatchmakingIntegrationStatusTests(unittest.TestCase):
    def test_status_does_not_claim_unverified_live_client_integration(self):
        status = MatchmakingService.status()
        self.assertEqual(status.domain_logic, "implemented_and_tested")
        self.assertTrue(status.simulation_api)
        self.assertIs(status.live_client_protocol, ClientProtocolStatus.NOT_REVERSED)
        self.assertIn("not yet verified", status.detail)


if __name__ == "__main__":
    unittest.main()
