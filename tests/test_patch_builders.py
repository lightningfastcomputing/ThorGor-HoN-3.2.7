import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


k2 = load("build_k2_v57", "patches/build_k2_v57.py")
k2_v63 = load("build_k2_v63", "patches/build_k2_v63_state_delivery.py")
k2_v64 = load("build_k2_v64", "patches/build_k2_v64_state_delivery.py")
k2_v65 = load("build_k2_v65", "patches/build_k2_v65_state_delivery.py")
k2_v66 = load("build_k2_v66", "patches/build_k2_v66_state_delivery.py")
k2_v67 = load("build_k2_v67", "patches/build_k2_v67_safe_reconciliation.py")
k2_v68 = load("build_k2_v68", "patches/build_k2_v68_roster_only_reconciliation.py")
k2_v75 = load(
    "build_k2_v75", "patches/build_k2_v75_hero_state_reconciliation.py"
)
k2_v76 = load(
    "build_k2_v76", "patches/build_k2_v76_world_ready_hero_state_reconciliation.py"
)
k2_v77 = load(
    "build_k2_v77", "patches/build_k2_v77_tail_recipient_hero_fix.py"
)
cgame = load("build_cgame_v61", "patches/build_cgame_v61_complete_registry_guard.py")


class PatchBuilderTests(unittest.TestCase):
    def test_k2_manifest_is_sorted_and_non_overlapping(self):
        previous_end = 0
        for offset, replacement_hex in k2.PATCHES:
            replacement = bytes.fromhex(replacement_hex)
            self.assertGreaterEqual(offset, previous_end)
            self.assertGreater(len(replacement), 0)
            previous_end = offset + len(replacement)

    def test_k2_source_and_output_hashes_are_distinct_sha256(self):
        self.assertEqual(
            k2.SOURCE_SHA256S,
            {k2.CLEAN_SOURCE_SHA256, k2.SANDBOXED_SOURCE_SHA256},
        )
        for source_hash in k2.SOURCE_SHA256S:
            self.assertRegex(source_hash, r"^[0-9A-F]{64}$")
            self.assertNotEqual(source_hash, k2.OUTPUT_SHA256)
        self.assertRegex(k2.OUTPUT_SHA256, r"^[0-9A-F]{64}$")

    def test_k2_clean_source_normalization_is_fixed_width_utf16(self):
        self.assertEqual(len(k2.LOCAL_AUTOPATCHER), k2.AUTOPATCHER_FIELD_SIZE)
        self.assertTrue(
            k2.LOCAL_AUTOPATCHER.startswith(
                "127.0.0.1/patcher/auto_patcher.php\0".encode("utf-16le")
            )
        )
        self.assertGreater(k2.AUTOPATCHER_OFFSET, 0)

    def test_k2_v63_hash_chain_and_hook_layout(self):
        self.assertEqual(k2_v63.SOURCE_SHA256, k2.OUTPUT_SHA256)
        self.assertRegex(k2_v63.OUTPUT_SHA256, r"^[0-9A-F]{64}$")
        self.assertNotEqual(k2_v63.SOURCE_SHA256, k2_v63.OUTPUT_SHA256)
        self.assertEqual(len(k2_v63.STRING_CALLS), 4)
        self.assertLess(k2_v63.SET_BLOCK_HOOK, k2_v63.BLOCK_CAVE)
        self.assertLess(k2_v63.STRING_CALLS[-1], k2_v63.STRING_CAVE)

    def test_k2_v63_rel32_targets_are_exact(self):
        for site in k2_v63.STRING_CALLS:
            encoded = k2_v63.call(site, k2_v63.STRING_CAVE)
            displacement = int.from_bytes(encoded[1:], "little", signed=True)
            self.assertEqual(site + 5 + displacement, k2_v63.STRING_CAVE)
        encoded = k2_v63.jump(k2_v63.SET_BLOCK_HOOK, k2_v63.BLOCK_CAVE)
        displacement = int.from_bytes(encoded[1:], "little", signed=True)
        self.assertEqual(k2_v63.SET_BLOCK_HOOK + 5 + displacement, k2_v63.BLOCK_CAVE)

    def test_k2_v64_hash_chain_and_scoped_queue_wrapper(self):
        self.assertEqual(k2_v64.SOURCE_SHA256, k2.OUTPUT_SHA256)
        self.assertRegex(k2_v64.OUTPUT_SHA256, r"^[0-9A-F]{64}$")
        self.assertNotEqual(k2_v64.OUTPUT_SHA256, k2_v63.OUTPUT_SHA256)
        self.assertLess(k2_v64.STRING_CAVE, k2_v64.BLOCK_QUEUE_WRAPPER)

        block_call = k2_v64.call(0x1000, k2_v64.BLOCK_QUEUE_WRAPPER)
        displacement = int.from_bytes(block_call[1:], "little", signed=True)
        self.assertEqual(0x1005 + displacement, k2_v64.BLOCK_QUEUE_WRAPPER)

        active_jz = k2_v64.jz(0x2000, k2_v64.QUEUE_BLOCK_EPILOGUE)
        displacement = int.from_bytes(active_jz[2:], "little", signed=True)
        self.assertEqual(0x2006 + displacement, k2_v64.QUEUE_BLOCK_EPILOGUE)

    def test_k2_v65_uses_authoritative_linked_recipient_wrapper(self):
        self.assertEqual(k2_v65.SOURCE_SHA256, k2.OUTPUT_SHA256)
        self.assertRegex(k2_v65.OUTPUT_SHA256, r"^[0-9A-F]{64}$")
        self.assertNotEqual(k2_v65.OUTPUT_SHA256, k2_v64.OUTPUT_SHA256)
        self.assertFalse(hasattr(k2_v65, "QUEUE_BLOCK_EPILOGUE"))
        self.assertFalse(hasattr(k2_v65, "jz"))

        wrapper_jump = k2_v65.jump(0x2000, k2_v65.QUEUE_BLOCK_BODY)
        displacement = int.from_bytes(wrapper_jump[1:], "little", signed=True)
        self.assertEqual(0x2005 + displacement, k2_v65.QUEUE_BLOCK_BODY)

    def test_k2_v66_reconciles_each_linked_client_revision(self):
        self.assertEqual(k2_v66.SOURCE_SHA256, k2.OUTPUT_SHA256)
        self.assertRegex(k2_v66.OUTPUT_SHA256, r"^[0-9A-F]{64}$")
        self.assertNotEqual(k2_v66.OUTPUT_SHA256, k2_v65.OUTPUT_SHA256)
        self.assertLess(k2_v66.PERIODIC_BLOCK_START, k2_v66.PERIODIC_BLOCK_RETURN)
        self.assertLess(k2_v66.PERIODIC_BLOCK_RETURN, k2_v66.RECONCILE_WRAPPER)

        wrapper_jump = k2_v66.jump(0x2000, k2_v66.QUEUE_BLOCK_BODY)
        displacement = int.from_bytes(wrapper_jump[1:], "little", signed=True)
        self.assertEqual(0x2005 + displacement, k2_v66.QUEUE_BLOCK_BODY)

    def test_k2_v67_restores_periodic_queue_readiness_guards(self):
        self.assertEqual(k2_v67.SOURCE_SHA256, k2_v66.SOURCE_SHA256)
        self.assertRegex(k2_v67.OUTPUT_SHA256, r"^[0-9A-F]{64}$")
        self.assertNotEqual(k2_v67.OUTPUT_SHA256, k2_v66.OUTPUT_SHA256)
        guarded = k2_v67.call(
            k2_v67.RECONCILE_QUEUE_CALL, k2_v67.ORIGINAL_QUEUE_BLOCK
        )
        displacement = int.from_bytes(guarded[1:], "little", signed=True)
        self.assertEqual(
            k2_v67.RECONCILE_QUEUE_CALL + 5 + displacement,
            k2_v67.ORIGINAL_QUEUE_BLOCK,
        )

    def test_k2_v68_reconciliation_is_limited_to_roster_blocks(self):
        self.assertEqual(k2_v68.SOURCE_SHA256, k2_v67.SOURCE_SHA256)
        self.assertEqual(k2_v68.V67_SHA256, k2_v67.OUTPUT_SHA256)
        self.assertRegex(k2_v68.OUTPUT_SHA256, r"^[0-9A-F]{64}$")
        self.assertNotEqual(k2_v68.OUTPUT_SHA256, k2_v67.OUTPUT_SHA256)

        entry = k2_v68.jump(k2_v68.RECONCILE_CLIENT_HEAD, k2_v68.ROSTER_GUARD)
        displacement = int.from_bytes(entry[1:], "little", signed=True)
        self.assertEqual(
            k2_v68.RECONCILE_CLIENT_HEAD + 5 + displacement,
            k2_v68.ROSTER_GUARD,
        )

        for site, condition in ((k2_v68.ROSTER_GUARD + 3, 0x82),
                                (k2_v68.ROSTER_GUARD + 12, 0x87)):
            branch = k2_v68.jcc(site, k2_v68.RECONCILE_DONE, condition)
            displacement = int.from_bytes(branch[2:], "little", signed=True)
            self.assertEqual(site + 6 + displacement, k2_v68.RECONCILE_DONE)

    def test_k2_v75_reconciles_only_traced_hero_blocks_through_guarded_queue(self):
        self.assertEqual(k2_v75.SOURCE_SHA256, k2_v65.OUTPUT_SHA256)
        self.assertRegex(k2_v75.OUTPUT_SHA256, r"^[0-9A-F]{64}$")
        self.assertNotEqual(k2_v75.OUTPUT_SHA256, k2_v75.SOURCE_SHA256)
        self.assertEqual(k2_v75.QUEUE_BLOCK, k2_v66.QUEUE_BLOCK)
        self.assertLess(k2_v75.PERIODIC_BLOCK_START, k2_v75.PERIODIC_BLOCK_RETURN)
        self.assertLess(k2_v75.PERIODIC_BLOCK_RETURN, k2_v75.RECONCILE_WRAPPER)

        guarded = k2_v75.call(0x2000, k2_v75.QUEUE_BLOCK)
        displacement = int.from_bytes(guarded[1:], "little", signed=True)
        self.assertEqual(0x2005 + displacement, k2_v75.QUEUE_BLOCK)

    def test_k2_v76_adds_world_loaded_gate_to_guarded_hero_reconciliation(self):
        self.assertEqual(k2_v76.SOURCE_SHA256, k2_v65.OUTPUT_SHA256)
        self.assertRegex(k2_v76.OUTPUT_SHA256, r"^[0-9A-F]{64}$")
        self.assertNotEqual(k2_v76.OUTPUT_SHA256, k2_v75.OUTPUT_SHA256)
        self.assertEqual(k2_v76.QUEUE_BLOCK, k2_v75.QUEUE_BLOCK)
        self.assertLess(k2_v76.PERIODIC_BLOCK_RETURN, k2_v76.RECONCILE_WRAPPER)

        guarded = k2_v76.call(0x2000, k2_v76.QUEUE_BLOCK)
        displacement = int.from_bytes(guarded[1:], "little", signed=True)
        self.assertEqual(0x2005 + displacement, k2_v76.QUEUE_BLOCK)

    def test_k2_v77_preserves_original_periodic_body_and_hooks_only_loop_tail(self):
        self.assertEqual(k2_v77.SOURCE_SHA256, k2_v65.OUTPUT_SHA256)
        self.assertRegex(k2_v77.OUTPUT_SHA256, r"^[0-9A-F]{64}$")
        self.assertNotEqual(k2_v77.OUTPUT_SHA256, k2_v76.OUTPUT_SHA256)
        self.assertEqual(k2_v77.QUEUE_BLOCK, k2_v75.QUEUE_BLOCK)
        self.assertEqual(k2_v77.TAIL_HOOK, k2_v75.PERIODIC_BLOCK_RETURN)

        tail_jump = k2_v77.jump(k2_v77.TAIL_HOOK, k2_v77.TAIL_WRAPPER)
        displacement = int.from_bytes(tail_jump[1:], "little", signed=True)
        self.assertEqual(k2_v77.TAIL_HOOK + 5 + displacement, k2_v77.TAIL_WRAPPER)

    def test_cgame_call_patch_shape(self):
        patch = cgame.call_patch(0x1000, 0x2000, 8)
        self.assertEqual(patch[0], 0xE8)
        self.assertEqual(patch[-3:], b"\x90\x90\x90")
        self.assertEqual(len(patch), 8)

    def test_cgame_hashes_and_stubs_are_present(self):
        self.assertRegex(cgame.SOURCE_HASH, r"^[0-9A-F]{64}$")
        self.assertRegex(cgame.OUTPUT_HASH, r"^[0-9A-F]{64}$")
        self.assertGreater(len(cgame.FINALIZE_STUB), 32)
        self.assertGreater(len(cgame.LOOKUP_STUB), 24)
        self.assertGreater(len(cgame.FALLBACK_STUB), 32)


if __name__ == "__main__":
    unittest.main()
