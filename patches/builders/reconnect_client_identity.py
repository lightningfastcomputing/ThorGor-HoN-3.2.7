"""Document the verified reconnect input stage.

The catalog applies the v28 instruction-level changes. Its narrow control repair
keeps the verified v25 player selection and transport behavior, then synchronizes
both the hero owner and retained player entity after the CPlayer adopts K2's
fresh client number. It does not alter shared player lookup or lobby admission.
"""
from __future__ import annotations

from pathlib import Path

from thorgor.patches.engine import sha256

SOURCE_SHA256 = "929FADD55C141946BC102704C06F41A4AAB74ABE1CC92DFE2E185C5A3B88C35B"
OUTPUT_SHA256 = SOURCE_SHA256


def build(source: Path, target: Path) -> str:
    data = source.read_bytes()
    digest = sha256(data)
    if digest != SOURCE_SHA256:
        raise ValueError("reconnect identity requires the capacity-patched game.dll")
    target.write_bytes(data)
    return digest
