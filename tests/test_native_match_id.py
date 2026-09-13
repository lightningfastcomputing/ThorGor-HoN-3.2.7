import unittest

from thorgor.game_manager.native_match_id import VERIFIED_GAME_DLL_SHA256S
from thorgor.patches.catalog import PatchCatalog


class NativeMatchIdVerificationTests(unittest.TestCase):
    def test_accepts_every_supported_game_dll_stage(self):
        catalog = PatchCatalog()
        capacity = catalog.get("dedicated.server_capacity")
        reconnect = catalog.get("dedicated.reconnect_client_identity")

        self.assertTrue(set(capacity.source_sha256) <= VERIFIED_GAME_DLL_SHA256S)
        self.assertIn(capacity.output_sha256, VERIFIED_GAME_DLL_SHA256S)
        self.assertIn(reconnect.output_sha256, VERIFIED_GAME_DLL_SHA256S)

    def test_reconnect_uses_stock_account_identity_comparison(self):
        reconnect = PatchCatalog().get("dedicated.reconnect_client_identity")
        account_match, client_number_guard = reconnect.operations
        self.assertEqual(account_match.replacement, bytes.fromhex("8B82580200003B470C757A"))
        self.assertEqual(client_number_guard.replacement, bytes.fromhex("EB1C909090909090"))
        self.assertEqual(client_number_guard.offset + 2 + 0x1C, 0x333FB)


if __name__ == "__main__":
    unittest.main()
