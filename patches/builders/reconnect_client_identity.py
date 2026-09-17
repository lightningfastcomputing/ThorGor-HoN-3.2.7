"""Keep game.dll's stock player identity path for reconnects.

The engine already supports reconnect correctly when K2 returns the original
native client number. ThorGor now supplies a persistent, authenticated K2
connection token on the first admission and again after a drop, so no player
map, team ownership, hero ownership, or CPlayer client number may be rewritten
inside game.dll.
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
