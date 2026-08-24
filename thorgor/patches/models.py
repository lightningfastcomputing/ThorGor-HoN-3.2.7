from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _hash(value: str, label: str) -> str:
    normalized = value.upper()
    if len(normalized) != 64 or any(c not in "0123456789ABCDEF" for c in normalized):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return normalized


@dataclass(frozen=True)
class WriteOperation:
    offset: int
    replacement: bytes
    expected: bytes | None = None
    address: str = "file_offset"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WriteOperation":
        address = data.get("address", "file_offset")
        if address not in {"file_offset", "rva"}:
            raise ValueError(f"unsupported address kind: {address}")
        replacement = bytes.fromhex(data["replacement"])
        expected = bytes.fromhex(data["expected"]) if data.get("expected") else None
        if not replacement:
            raise ValueError("patch operation replacement cannot be empty")
        if expected is not None and len(expected) != len(replacement):
            raise ValueError("expected and replacement byte lengths must match")
        return cls(
            offset=int(str(data["offset"]), 0),
            replacement=replacement,
            expected=expected,
            address=address,
        )


@dataclass(frozen=True)
class PatchManifest:
    patch_id: str
    binary: str
    version: str
    source_sha256: tuple[str, ...]
    output_sha256: str
    reason: str
    observed_failure: str
    discovered: str
    evidence: tuple[str, ...]
    operations: tuple[WriteOperation, ...]
    legacy_builder: Path | None
    manifest_path: Path

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: Path) -> "PatchManifest":
        patch_id = data["id"]
        if not patch_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for c in patch_id):
            raise ValueError(f"invalid patch id: {patch_id!r}")
        source = data["source_sha256"]
        source_hashes = (source,) if isinstance(source, str) else tuple(source)
        implementation = data.get("implementation", {})
        legacy = implementation.get("path") if implementation.get("kind") == "legacy_builder" else None
        operations = tuple(WriteOperation.from_dict(item) for item in data.get("operations", ()))
        if not operations and not legacy:
            raise ValueError(f"{patch_id} has no patch implementation")
        return cls(
            patch_id=patch_id,
            binary=data["binary"],
            version=data["version"],
            source_sha256=tuple(_hash(value, "source_sha256") for value in source_hashes),
            output_sha256=_hash(data["output_sha256"], "output_sha256"),
            reason=data["reason"],
            observed_failure=data["observed_failure"],
            discovered=data["discovered"],
            evidence=tuple(data.get("evidence", ())),
            operations=operations,
            legacy_builder=Path(legacy) if legacy else None,
            manifest_path=path,
        )
