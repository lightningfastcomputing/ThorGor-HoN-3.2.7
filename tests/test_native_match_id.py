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

    def test_reconnect_nonmatch_branch_rejoins_player_scan_on_instruction_boundary(self):
        reconnect = PatchCatalog().get("dedicated.reconnect_client_identity")
        operation = reconnect.operations[0]
        replacement = operation.replacement

        jump_offset = replacement.index(b"\x75")
        displacement = replacement[jump_offset + 1]
        jump_rva = operation.offset + jump_offset
        self.assertEqual(jump_rva + 2 + displacement, 0x33428)


if __name__ == "__main__":
    unittest.main()
