"""Keep game.dll's stock player identity path for reconnects.

The stock reconnect predicates require both the original account and native
client number. The paired K2 admission patch preserves those values and retires
the disconnected transport's number before reuse. No player map, team ownership,
hero ownership, or CPlayer client number is rewritten inside game.dll.
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
