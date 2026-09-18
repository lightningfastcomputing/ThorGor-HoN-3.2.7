import unittest

from thorgor.game_manager.native_match_id import (
    VERIFIED_GAME_DLL_SHA256S,
    read_native_player_map,
)
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

    def test_k2_hook_and_capture_fit_reserved_caves(self):
        stub = creator_authority.authority_stub()
        self.assertLessEqual(len(stub), 0x40)
        self.assertLessEqual(len(creator_authority.capture_stub()), 0x40)
        self.assertLessEqual(len(creator_authority.allocator_stub()), 0x140)
        self.assertLessEqual(len(creator_authority.connection_lookup_guard_stub()), 0x40)

    def test_stock_allocator_is_unchanged_and_local_call_is_wrapped(self):
        patched_rvas = {rva for rva, _, _ in creator_authority.operations()}
        self.assertNotIn(0x2F1B95, patched_rvas)
        self.assertNotIn(0x2F1BA7, patched_rvas)
        self.assertNotIn(0x2F1BAD, patched_rvas)
        self.assertIn(creator_authority.ALLOCATOR_CALL_RVA, patched_rvas)

    def test_passive_player_map_walk_preserves_native_candidate_order(self):
        class FakeProcess:
            def __init__(self, u32, u8):
                self.u32 = u32
                self.u8 = u8

            def read_u32(self, address):
                return self.u32[address]

            def read_u8(self, address):
                return self.u8[address]

        game, head, first, second = 0x100000, 0x200000, 0x200100, 0x200200
        player1, player2 = 0x300100, 0x300200
        u32 = {
            game + 0x100: head,
            head: first,
            first: head, first + 4: second, first + 8: head, first + 0x10: player1,
            second: first, second + 4: head, second + 8: head, second + 0x10: player2,
            player1 + 0x6C: 0, player1 + 0x258: 0x80000002, player1 + 0x35C: 0x11,
            player2 + 0x6C: 1, player2 + 0x258: 0x80000003, player2 + 0x35C: 0x22,
        }
        u8 = {player1 + 0x35A: 1, player2 + 0x35A: 2}

        players = read_native_player_map(FakeProcess(u32, u8), game)

        self.assertEqual([entry["native_client_number"] for entry in players], [0, 1])
        self.assertEqual([entry["account_id_low30"] for entry in players], [2, 3])
        self.assertEqual([entry["connection_status"] for entry in players], [1, 2])


if __name__ == "__main__":
    unittest.main()
