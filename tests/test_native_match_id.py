import unittest

from thorgor.game_manager.native_match_id import VERIFIED_GAME_DLL_SHA256S
from thorgor.patches.builders import creator_authority
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
        self.assertEqual(client_number_guard.replacement, bytes.fromhex("8B406C3B47087416"))
        self.assertEqual(client_number_guard.offset + 8 + 0x16, 0x333FB)

    def test_k2_hook_preserves_account_without_mutating_connection_id(self):
        stub = creator_authority.authority_stub()
        self.assertTrue(stub.startswith(bytes.fromhex("8B45B889430C")))
        self.assertLessEqual(len(stub), 0x40)

    def test_k2_allocator_matches_retained_record_by_nonzero_account(self):
        operations = {rva: replacement for rva, _, replacement in creator_authority.operations()}
        self.assertEqual(
            operations[creator_authority.GENERATE_ID_RECONNECT_MARKER_RVA],
            bytes.fromhex("66833B7F7506"),
        )
        self.assertEqual(
            operations[creator_authority.GENERATE_ID_COMPARE_RVA],
            bytes.fromhex("39680490"),
        )


if __name__ == "__main__":
    unittest.main()
