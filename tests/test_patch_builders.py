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
