"""Creator-only native authority on the exact v77 K2 milestone.

All addresses are RVAs. K2 3.2.7.1's text mapping also uses identical file
offsets here; conversion is still explicit. The paired authenticated proxy
owns C0 marker bit zero. The remaining request bits never grant authority.
"""
from __future__ import annotations

import struct
from pathlib import Path

from thorgor.patches.engine import _rva_to_file, sha256

SOURCE_SHA256 = "25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026"
OUTPUT_SHA256 = "21AD692656419D6483DE1B93A16DFB7E04BC7C2ACB6EBDA00D6F7A54A13493F0"
MARKER_REJECTION_RVA = 0x2F5982
HOOK_RVA = 0x2F5AD6
RETURN_RVA = 0x2F5ADD
CAVE_RVA = 0x70D740
PROMOTION_RVA = 0x2F8E1E


def jump(source: int, target: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target - source - 5)


def authority_stub() -> bytes:
    code = bytes.fromhex(
        "83a3cc000000f8"  # clear the composite local/admin/host bits
        "f645ef01"        # test byte [ebp-0x11],1: approved creator only
        "7407"            # skip granting creator bits for ordinary joiners
        "838bcc00000007"  # retain the creator's original flags
    )
    return code + jump(CAVE_RVA + len(code), RETURN_RVA)


def operations() -> tuple[tuple[int, bytes, bytes], ...]:
    code = authority_stub()
    return (
        # Enter the proven local constructor even for a creator-marked C0.
        (MARKER_REJECTION_RVA, bytes.fromhex("0f859a020000"), b"\x90" * 6),
        (HOOK_RVA, bytes.fromhex("838bcc00000007"), jump(HOOK_RVA, CAVE_RVA) + b"\x90\x90"),
        (CAVE_RVA, bytes(0x40), code.ljust(0x40, b"\0")),
        # AuthSuccess's legacy account/roster fallback must not override the
        # master decision. Host-flag testing and NETCMD_GAME_HOST stay native.
        (PROMOTION_RVA, bytes.fromhex("838dcc00000001"), b"\x90" * 7),
    )


def build(source: Path, target: Path) -> str:
    data = bytearray(source.read_bytes())
    if sha256(data) != SOURCE_SHA256:
        raise ValueError("creator authority requires the verified v77 K2 milestone")
    for rva, expected, replacement in operations():
        offset = _rva_to_file(data, rva)
        if data[offset:offset + len(expected)] != expected:
            raise ValueError(f"unexpected authority patch bytes at RVA 0x{rva:X}")
        data[offset:offset + len(replacement)] = replacement
    digest = sha256(data)
    if digest != OUTPUT_SHA256:
        raise ValueError(f"unexpected creator-authority output hash {digest}")
    target.write_bytes(data)
    return digest
