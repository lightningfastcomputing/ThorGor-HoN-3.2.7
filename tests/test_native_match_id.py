import unittest

from thorgor.game_manager.native_match_id import VERIFIED_GAME_DLL_SHA256S
from thorgor.patches.builders import creator_authority, reconnect_client_identity
from thorgor.patches.catalog import PatchCatalog


class NativeMatchIdVerificationTests(unittest.TestCase):
    def test_accepts_every_supported_game_dll_stage(self):
        catalog = PatchCatalog()
        capacity = catalog.get("dedicated.server_capacity")
        reconnect = catalog.get("dedicated.reconnect_client_identity")

        self.assertTrue(set(capacity.source_sha256) <= VERIFIED_GAME_DLL_SHA256S)
        self.assertIn(capacity.output_sha256, VERIFIED_GAME_DLL_SHA256S)
        self.assertIn(reconnect.output_sha256, VERIFIED_GAME_DLL_SHA256S)

    def test_reconnect_preserves_stock_game_player_identity(self):
        reconnect = PatchCatalog().get("dedicated.reconnect_client_identity")
        self.assertFalse(reconnect.operations)
        self.assertEqual(reconnect_client_identity.SOURCE_SHA256, reconnect.source_sha256[0])
        self.assertEqual(reconnect_client_identity.OUTPUT_SHA256, reconnect.output_sha256)
        self.assertEqual(reconnect_client_identity.OUTPUT_SHA256, reconnect_client_identity.SOURCE_SHA256)

    def test_k2_hook_authenticates_persistent_connection_token(self):
        stub = creator_authority.authority_stub()
        self.assertTrue(stub.startswith(bytes.fromhex("8B45B8A90000004074078B55E866895314")))
        self.assertLessEqual(len(stub), 0x40)

    def test_k2_allocator_changes_only_retired_record_number_compare(self):
        patched_rvas = {rva for rva, _, _ in creator_authority.operations()}
        self.assertNotIn(0x2F1B95, patched_rvas)
        self.assertNotIn(0x2F1BA7, patched_rvas)
        self.assertIn(0x2F1BAD, patched_rvas)


if __name__ == "__main__":
    unittest.main()
