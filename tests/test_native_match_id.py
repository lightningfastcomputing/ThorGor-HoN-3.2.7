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
        self.assertEqual(client_number_guard.replacement, bytes.fromhex("8B570889506CEB16"))
        self.assertEqual(client_number_guard.offset + 8 + 0x16, 0x333FB)

    def test_k2_hook_separates_normal_admission_from_reconnect(self):
        stub = creator_authority.authority_stub()
        self.assertTrue(stub.startswith(bytes.fromhex("8B45B825FFFFFFBF89430C")))
        self.assertLessEqual(len(stub), 0x40)

    def test_k2_allocator_remains_stock(self):
        patched_rvas = {rva for rva, _, _ in creator_authority.operations()}
        self.assertNotIn(0x2F1B95, patched_rvas)
        self.assertNotIn(0x2F1BA7, patched_rvas)


if __name__ == "__main__":
    unittest.main()
