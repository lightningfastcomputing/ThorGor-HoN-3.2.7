import hashlib
import tempfile
import unittest
from pathlib import Path

from thorgor.patches.installer import (
    CGAME_STOCK_BACKUP,
    K2_LINKED_BACKUP,
    K2_PRE_RECIPIENT_BACKUP,
    K2_STOCK_BACKUP,
    install_cgame,
    install_k2,
)
from thorgor.patches.models import PatchManifest, WriteOperation


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def manifest(patch_id: str, binary: str, source: bytes, output: bytes, offset: int) -> PatchManifest:
    return PatchManifest(
        patch_id=patch_id,
        binary=binary,
        version="fixture",
        source_sha256=(digest(source),),
        output_sha256=digest(output),
        reason="fixture",
        observed_failure="fixture",
        discovered="2026-08-24",
        legacy_revision="v0",
        evidence=(),
        operations=(
            WriteOperation(offset, output[offset : offset + 1], source[offset : offset + 1]),
        ),
        builder=None,
        manifest_path=Path("fixture.json"),
    )


class FixtureCatalog:
    def __init__(self):
        stock = b"ABCD"
        redirected = b"AXCD"
        linked = b"AXYD"
        final = b"AXYZ"
        cgame_stock = b"1234"
        cgame_final = b"1A34"
        self.manifests = {
            "client.server_redirects": manifest(
                "client.server_redirects", "k2.dll", stock, redirected, 1
            ),
            "dedicated.state_delivery_linked": manifest(
                "dedicated.state_delivery_linked", "k2.dll", redirected, linked, 2
            ),
            "dedicated.hero_state_recipient_fix": manifest(
                "dedicated.hero_state_recipient_fix", "k2.dll", linked, final, 3
            ),
            "dedicated.complete_registry_guard": manifest(
                "dedicated.complete_registry_guard", "cgame.dll", cgame_stock, cgame_final, 1
            ),
        }

    def get(self, patch_id: str):
        return self.manifests[patch_id]


class PatchInstallerTests(unittest.TestCase):
    def test_k2_clean_install_reproduces_chain_and_verified_backups(self):
        catalog = FixtureCatalog()
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            target = home / "k2.dll"
            target.write_bytes(b"ABCD")
            install_k2(home, catalog)
            self.assertEqual(target.read_bytes(), b"AXYZ")
            self.assertEqual((home / K2_STOCK_BACKUP).read_bytes(), b"ABCD")
            self.assertEqual((home / K2_LINKED_BACKUP).read_bytes(), b"AXYD")
            self.assertEqual((home / K2_PRE_RECIPIENT_BACKUP).read_bytes(), b"AXYD")
            self.assertIn("already installed", install_k2(home, catalog))

    def test_k2_recovers_from_semantic_linked_baseline(self):
        catalog = FixtureCatalog()
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "k2.dll").write_bytes(b"unsupported")
            (home / K2_LINKED_BACKUP).write_bytes(b"AXYD")
            install_k2(home, catalog)
            self.assertEqual((home / "k2.dll").read_bytes(), b"AXYZ")

    def test_k2_keeps_the_supported_recipient_build_installed(self):
        catalog = FixtureCatalog()
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            target = home / "k2.dll"
            target.write_bytes(b"AXYZ")
            (home / K2_LINKED_BACKUP).write_bytes(b"AXYD")
            install_k2(home, catalog)
            self.assertEqual(target.read_bytes(), b"AXYZ")

    def test_cgame_clean_install_and_idempotence(self):
        catalog = FixtureCatalog()
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            game = home / "game"
            game.mkdir()
            target = game / "cgame.dll"
            target.write_bytes(b"1234")
            install_cgame(home, catalog)
            self.assertEqual(target.read_bytes(), b"1A34")
            self.assertEqual((game / CGAME_STOCK_BACKUP).read_bytes(), b"1234")
            self.assertIn("already installed", install_cgame(home, catalog))


if __name__ == "__main__":
    unittest.main()
