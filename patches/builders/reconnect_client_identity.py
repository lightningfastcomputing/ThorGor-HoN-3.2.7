"""Document the verified reconnect identity and snapshot stages.

The catalog applies the v32 instruction-level changes. It retains v31's verified
identity handoff, gameplay-only lookup and native CPlayer::Connected transition,
then adds the same stock-first fallback inside ProcessClientSnapshot. Shared
lookup, team rosters, ordinary lobby admission and initial team joining stay
untouched.
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
