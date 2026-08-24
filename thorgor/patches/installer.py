from __future__ import annotations

import os
import shutil
from pathlib import Path

from .catalog import PatchCatalog
from .engine import apply_patch, sha256


K2_STOCK_BACKUP = "k2.dll.thorgor_stock_3.2.7.1"
K2_LINKED_BACKUP = "k2.dll.thorgor_linked_delivery_baseline"
K2_HISTORICAL_LINKED_BACKUP = "k2.dll.thorgor_v65_before_v75"
K2_PRE_RECIPIENT_BACKUP = "k2.dll.thorgor_before_recipient_fix"
CGAME_STOCK_BACKUP = "cgame.dll.thorgor_stock_3.2.7.1"


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes())


def _verified(path: Path, hashes: tuple[str, ...] | set[str]) -> bool:
    return path.is_file() and file_hash(path) in hashes


def _replace_from_patch(manifest, source: Path, target: Path) -> None:
    candidate = target.with_name(target.name + ".thorgor.new")
    candidate.unlink(missing_ok=True)
    try:
        apply_patch(manifest, source, candidate)
        os.replace(candidate, target)
    finally:
        candidate.unlink(missing_ok=True)


def _preserve_verified(source: Path, backup: Path, expected_hash: str) -> None:
    if backup.exists():
        if not _verified(backup, {expected_hash}):
            raise ValueError(f"existing ThorGor backup has an unexpected hash: {backup}")
        return
    shutil.copy2(source, backup)
    if file_hash(backup) != expected_hash:
        backup.unlink(missing_ok=True)
        raise ValueError(f"could not verify new ThorGor backup: {backup}")


def install_k2(hon_home: Path, catalog: PatchCatalog | None = None) -> str:
    catalog = catalog or PatchCatalog()
    redirects = catalog.get("client.server_redirects")
    linked = catalog.get("dedicated.state_delivery_linked")
    recipient = catalog.get("dedicated.hero_state_recipient_fix")
    target = hon_home / "k2.dll"
    if not target.is_file():
        raise FileNotFoundError(f"k2.dll not found: {target}")

    current = file_hash(target)
    if current == recipient.output_sha256:
        return "K2 recipient hero-state fix is already installed."

    linked_source: Path | None = target if current == linked.output_sha256 else None
    if linked_source is None:
        candidates = (
            hon_home / K2_LINKED_BACKUP,
            hon_home / K2_HISTORICAL_LINKED_BACKUP,
        )
        linked_source = next(
            (path for path in candidates if _verified(path, {linked.output_sha256})),
            None,
        )

    if linked_source is None:
        stock_backup = hon_home / K2_STOCK_BACKUP
        stock_hashes = set(redirects.source_sha256)
        if current in stock_hashes:
            _preserve_verified(target, stock_backup, current)
        if not _verified(stock_backup, stock_hashes):
            raise ValueError(
                "A verified stock HoN 3.2.7.1 k2.dll is required to rebuild the patch chain. "
                f"Expected it at {stock_backup}."
            )
        _replace_from_patch(redirects, stock_backup, target)
        _replace_from_patch(linked, target, target)
        linked_source = target

    semantic_linked = hon_home / K2_LINKED_BACKUP
    _preserve_verified(linked_source, semantic_linked, linked.output_sha256)
    shutil.copy2(target, hon_home / K2_PRE_RECIPIENT_BACKUP)
    _replace_from_patch(recipient, linked_source, target)
    return "Installed K2 recipient hero-state fix from the verified linked-delivery baseline."


def install_cgame(hon_home: Path, catalog: PatchCatalog | None = None) -> str:
    catalog = catalog or PatchCatalog()
    guard = catalog.get("dedicated.complete_registry_guard")
    target = hon_home / "game" / "cgame.dll"
    backup = hon_home / "game" / CGAME_STOCK_BACKUP
    if not target.is_file():
        raise FileNotFoundError(f"cgame.dll not found: {target}")
    current = file_hash(target)
    if current == guard.output_sha256:
        return "cgame registry guard is already installed."
    stock_hashes = set(guard.source_sha256)
    if current in stock_hashes:
        _preserve_verified(target, backup, current)
    if not _verified(backup, stock_hashes):
        raise ValueError(
            "A verified stock HoN 3.2.7.1 cgame.dll is required. "
            f"Expected it at {backup}."
        )
    _replace_from_patch(guard, backup, target)
    return "Installed cgame complete-registry guard from the verified stock binary."


def install_supported_patches(hon_home: Path) -> tuple[str, str]:
    hon_home = hon_home.expanduser().resolve()
    return install_k2(hon_home), install_cgame(hon_home)


def verify_supported_install(hon_home: Path) -> tuple[str, str]:
    catalog = PatchCatalog()
    expected = (
        (hon_home / "k2.dll", catalog.get("dedicated.hero_state_recipient_fix").output_sha256),
        (hon_home / "game" / "cgame.dll", catalog.get("dedicated.complete_registry_guard").output_sha256),
    )
    verified = []
    for path, wanted in expected:
        if not path.is_file():
            raise FileNotFoundError(f"installed binary is missing: {path}")
        actual = file_hash(path)
        if actual != wanted:
            raise ValueError(f"installed binary hash mismatch: {path} ({actual})")
        verified.append(f"{path.name} {actual}")
    return tuple(verified)
