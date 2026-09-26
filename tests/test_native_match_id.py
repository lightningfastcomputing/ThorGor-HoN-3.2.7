import unittest

from thorgor.game_manager.native_match_id import (
    VERIFIED_GAME_DLL_SHA256S,
    read_native_player_map,
)
from thorgor.patches.builders import creator_authority
from thorgor.patches.catalog import PatchCatalog
from tools.build_reconnect_connected_state_stub import build as build_connected_state_stub
from tools.build_reconnect_snapshot_identity_stub import build as build_snapshot_identity_stub


class NativeMatchIdVerificationTests(unittest.TestCase):
    def test_accepts_every_supported_game_dll_stage(self):
        catalog = PatchCatalog()
        capacity = catalog.get("dedicated.server_capacity")
        reconnect = catalog.get("dedicated.reconnect_client_identity")

        self.assertTrue(set(capacity.source_sha256) <= VERIFIED_GAME_DLL_SHA256S)
        self.assertIn(capacity.output_sha256, VERIFIED_GAME_DLL_SHA256S)
        self.assertIn(reconnect.output_sha256, VERIFIED_GAME_DLL_SHA256S)

    def test_reconnect_preserves_identity_and_restores_connected_state(self):
        reconnect = PatchCatalog().get("dedicated.reconnect_client_identity")
        account_match, control_hook, *remaining = reconnect.operations
        by_offset = {operation.offset: operation for operation in remaining}
        control_caves = [operation for operation in remaining if 0x15691 <= operation.offset <= 0x15756]
        section_growth = next(operation for operation in remaining if operation.address == "file_offset")
        command_hook = by_offset[0x47907]
        command_cave = by_offset[0x73B00]
        connected_state_cave = by_offset[0x73C00]
        snapshot_hook = by_offset[0x2DD32]
        snapshot_cave = by_offset[0x73D00]
        self.assertEqual(account_match.replacement, bytes.fromhex("8B82580200003B470C757A"))
        self.assertEqual(control_hook.replacement, bytes.fromhex("E91E080400909090"))
        self.assertEqual(control_caves[0].replacement[:6], bytes.fromhex("8B570889506C"))
        self.assertTrue(any(bytes.fromhex("899044040000") in op.replacement for op in control_caves))
        self.assertTrue(any(bytes.fromhex("89913C020000") in op.replacement for op in control_caves))
        resume = next(op for op in control_caves if op.offset == 0x15725)
        self.assertEqual(resume.replacement[:5], bytes.fromhex("E9D1DC0100"))
        self.assertEqual(section_growth.address, "file_offset")
        self.assertEqual(section_growth.offset, 0x1F0)
        self.assertEqual(command_hook.offset, 0x47907)
        self.assertEqual(command_hook.replacement, bytes.fromhex("E9F4C102009090"))
        self.assertEqual(command_cave.offset, 0x73B00)
        self.assertIn(bytes.fromhex("8B5F6C3B5D44"), command_cave.replacement)
        self.assertEqual(connected_state_cave.offset, 0x73C00)
        self.assertEqual(connected_state_cave.replacement, build_connected_state_stub())
        self.assertIn(bytes.fromhex("6681A05A030000FEFF"), connected_state_cave.replacement)
        self.assertIn(bytes.fromhex("6683885A03000040"), connected_state_cave.replacement)
        self.assertIn(bytes.fromhex("C780A4030000FFFFFFFF"), connected_state_cave.replacement)
        self.assertEqual(snapshot_hook.replacement, bytes.fromhex("E9C95F04009090"))
        self.assertEqual(snapshot_cave.replacement, build_snapshot_identity_stub())
        self.assertIn(bytes.fromhex("39786C"), snapshot_cave.replacement)

    def test_v14_k2_hook_fits_reserved_cave(self):
        stub = creator_authority.authority_stub()
        self.assertTrue(stub.startswith(bytes.fromhex("8B8538FDFFFF25FFFFFFBF89430C")))
        self.assertLessEqual(len(stub), 0x40)
        self.assertLessEqual(len(creator_authority.account_capture_stub()), 0x40)
        self.assertLessEqual(len(creator_authority.managed_local_client_stop_stub()), 0x20)

    def test_v14_leaves_stock_allocator_and_transport_lookup_untouched(self):
        patched_rvas = {rva for rva, _, _ in creator_authority.operations()}
        self.assertNotIn(0x2F1B95, patched_rvas)
        self.assertNotIn(0x2F1BA7, patched_rvas)
        self.assertNotIn(0x2F1BAD, patched_rvas)
        self.assertNotIn(0x2F8E63, patched_rvas)
        self.assertNotIn(0x70D4EA, patched_rvas)

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
