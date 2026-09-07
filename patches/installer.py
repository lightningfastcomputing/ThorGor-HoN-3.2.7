from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .catalog import PatchCatalog
from .engine import apply_patch, sha256
from .client.matchmaking_ui import install_matchmaking_overlay, verify_matchmaking_overlay


K2_STOCK_BACKUP = "k2.dll.thorgor_stock_3.2.7.1"
K2_LINKED_BACKUP = "k2.dll.thorgor_linked_delivery_baseline"
K2_HISTORICAL_LINKED_BACKUP = "k2.dll.thorgor_v65_before_v75"
K2_PRE_RECIPIENT_BACKUP = "k2.dll.thorgor_before_recipient_fix"
K2_EXPERIMENTAL_RECIPIENT_BACKUP = "k2.dll.thorgor_experimental_v77"
CGAME_STOCK_BACKUP = "cgame.dll.thorgor_stock_3.2.7.1"
CGAME_REJECTED_TEAM_CHAT_SHA256 = "1CFA354C6B1E0DF780D22BF40DAB13E9756472FA13F32A466F461687C472DFDF"


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


def _install_k2_recipient(hon_home: Path, catalog: PatchCatalog | None = None) -> str:
    catalog = catalog or PatchCatalog()
    redirects = catalog.get("client.server_redirects")
    linked = catalog.get("dedicated.state_delivery_linked")
    recipient = catalog.get("dedicated.hero_state_recipient_fix")
    target = hon_home / "k2.dll"
    if not target.is_file():
        raise FileNotFoundError(f"k2.dll not found: {target}")

    current = file_hash(target)
    if current == recipient.output_sha256:
        return "K2 v77 tail-recipient hero-state fix is already installed."

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
    if linked_source.resolve() != target.resolve():
        shutil.copy2(linked_source, target)
    if file_hash(target) != linked.output_sha256:
        raise ValueError("could not install the verified K2 linked-delivery baseline")
    _preserve_verified(
        target,
        hon_home / K2_PRE_RECIPIENT_BACKUP,
        linked.output_sha256,
    )
    _replace_from_patch(recipient, target, target)
    if file_hash(target) != recipient.output_sha256:
        raise ValueError("could not install the verified K2 v77 recipient fix")
    return "Installed K2 v77 tail-recipient hero-state delivery from the verified v65 baseline."


def install_k2(hon_home: Path, catalog: PatchCatalog | None = None) -> str:
    """Build the entire milestone chain before replacing any installed DLL."""
    catalog = catalog or PatchCatalog()
    authority = catalog.get("dedicated.creator_authority")
    target = hon_home / "k2.dll"
    current = file_hash(target)
    if current == authority.output_sha256:
        return "K2 creator-only lobby authority is already installed."
    with tempfile.TemporaryDirectory(prefix="thorgor-k2-") as directory:
        staged = Path(directory)
        shutil.copy2(target, staged / target.name)
        for name in (K2_STOCK_BACKUP, K2_LINKED_BACKUP, K2_HISTORICAL_LINKED_BACKUP):
            if (hon_home / name).is_file():
                shutil.copy2(hon_home / name, staged / name)
        _install_k2_recipient(staged, catalog)
        # Validate the final output before preserving/installing anything.
        apply_patch(authority, staged / "k2.dll", staged / "candidate.dll")
        _preserve_verified(target, hon_home / f"k2.dll.thorgor_before_{current.lower()}", current)
        for name in (K2_STOCK_BACKUP, K2_LINKED_BACKUP):
            if (staged / name).is_file():
                _preserve_verified(staged / name, hon_home / name, file_hash(staged / name))
        _preserve_verified(
            staged / "k2.dll", hon_home / "k2.dll.thorgor_v77_baseline",
            authority.source_sha256[0],
        )
        _replace_from_patch(authority, staged / "k2.dll", target)
    return "Installed creator-only lobby authority on the verified K2 v77 milestone."


def install_game_capacity(hon_home: Path, catalog: PatchCatalog | None = None) -> str:
    catalog = catalog or PatchCatalog()
    capacity = catalog.get("dedicated.server_capacity")
    target = hon_home / "game" / "game.dll"
    backup = target.with_name("game.dll.thorgor_stock_3.2.7.1")
    current = file_hash(target)
    if current == capacity.output_sha256:
        return "Native ten-client capacity is already installed."
    source = target if current in capacity.source_sha256 else backup
    if not _verified(source, set(capacity.source_sha256)):
        raise ValueError("A verified stock game.dll is required for native multiplayer capacity")
    # Build before replacing and preserve the previous installation verbatim.
    with tempfile.TemporaryDirectory(prefix="thorgor-capacity-") as directory:
        candidate = Path(directory) / "game.dll"
        apply_patch(capacity, source, candidate)
        _preserve_verified(target, target.with_name(f"game.dll.thorgor_before_{current.lower()}"), current)
        _preserve_verified(source, backup, capacity.source_sha256[0])
        _replace_from_patch(capacity, backup, target)
    return "Installed native ten-client capacity for ordinary joiners."


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
    if current == CGAME_REJECTED_TEAM_CHAT_SHA256:
        return "Removed rejected v78 chat experiment and restored the cgame registry guard."
    return "Installed cgame complete-registry guard from the verified stock binary."


def install_supported_patches(hon_home: Path) -> tuple[str, ...]:
    hon_home = hon_home.expanduser().resolve()
    return install_game_capacity(hon_home), install_k2(hon_home), install_cgame(hon_home), install_matchmaking_overlay(hon_home)


def verify_supported_install(hon_home: Path) -> tuple[str, ...]:
    catalog = PatchCatalog()
    expected = (
        (hon_home / "k2.dll", catalog.get("dedicated.creator_authority").output_sha256),
        (hon_home / "game" / "game.dll", catalog.get("dedicated.server_capacity").output_sha256),
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
    verified.append(verify_matchmaking_overlay(hon_home))
    return tuple(verified)
