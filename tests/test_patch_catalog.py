import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from thorgor.patches.catalog import PatchCatalog
from thorgor.patches.engine import apply_patch
from thorgor.patches.models import PatchManifest


ROOT = Path(__file__).resolve().parents[1]


class PatchCatalogTests(unittest.TestCase):
    def test_every_stable_builder_has_one_named_manifest(self):
        manifests = PatchCatalog().all()
        builders = {
            manifest.builder.as_posix()
            for manifest in manifests
            if manifest.builder is not None
        }
        expected = {
            path.relative_to(ROOT / "thorgor").as_posix()
            for path in (ROOT / "thorgor" / "patches" / "builders").glob("*.py")
            if path.name != "__init__.py"
        }
        self.assertEqual(builders, expected)
        self.assertEqual(len(manifests), 12)

    def test_production_v77_patch_is_fully_declarative(self):
        manifest = PatchCatalog().get("dedicated.hero_state_recipient_fix")
        self.assertEqual(manifest.legacy_revision, "v77")
        self.assertIsNone(manifest.builder)
        self.assertEqual(len(manifest.operations), 2)
        self.assertEqual(manifest.operations[0].offset, 0x2F3E02)
        self.assertEqual(manifest.operations[1].offset, 0x70D6C0)

    def test_manifest_has_maintenance_evidence(self):
        for manifest in PatchCatalog().all():
            self.assertNotRegex(manifest.patch_id, r"_v\d+$")
            self.assertRegex(manifest.legacy_revision or "", r"^v\d+$")
            self.assertTrue(manifest.reason, manifest.patch_id)
            self.assertTrue(manifest.observed_failure, manifest.patch_id)
            self.assertRegex(manifest.discovered, r"^20\d\d-\d\d-\d\d$")
            self.assertTrue(manifest.evidence, manifest.patch_id)
            for evidence in manifest.evidence:
                self.assertTrue((ROOT / evidence).is_file(), f"{manifest.patch_id}: {evidence}")

    def test_declarative_engine_guards_original_and_output_hashes(self):
        source_bytes = b"ABCD"
        output_bytes = b"AXYD"
        data = {
            "id": "test.operation",
            "binary": "fixture.bin",
            "version": "test",
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
            "reason": "test",
            "observed_failure": "test",
            "discovered": "2026-08-24",
            "evidence": ["tests/test_patch_catalog.py"],
            "operations": [{"offset": "0x1", "expected": "4243", "replacement": "5859"}]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.bin"
            target = root / "target.bin"
            source.write_bytes(source_bytes)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            manifest = PatchManifest.from_dict(data, manifest_path)
            self.assertEqual(apply_patch(manifest, source, target), data["output_sha256"].upper())
            self.assertEqual(target.read_bytes(), output_bytes)


if __name__ == "__main__":
    unittest.main()
