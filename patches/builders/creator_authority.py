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
OUTPUT_SHA256 = "80C397409F857218F7D0D2692B70AC5C34194389C22E3C8E240466D6AA5CC02B"
RECONNECT_CONNECTION_ID = 0x7F
GENERATE_ID_RECONNECT_MARKER_RVA = 0x2F1BA7
GENERATE_ID_COMPARE_RVA = 0x2F1BAD
MARKER_REJECTION_RVA = 0x2F5982
HOOK_RVA = 0x2F5AD6
RETURN_RVA = 0x2F5ADD
CAVE_RVA = 0x70D740
PROMOTION_RVA = 0x2F8E1E
ACCOUNT_RESET_RVA = 0x2F8E50


def jump(source: int, target: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target - source - 5)


def authority_stub() -> bytes:
    code = bytes.fromhex(
        "8b45b8"          # load the authenticated local-only account identity
        "89430c"          # retain it in CClientConnection for CPlayer creation/reconnect
        "f645ef02"        # test authenticated proxy reconnect marker bit
        "7406"            # leave first-time admissions connectionless
        "66c743147f00"    # give only reconnect admission an allocator lookup sentinel
        "83a3cc000000f8"  # clear the composite local/admin/host bits
        "f645ef01"        # test byte [ebp-0x11],1: approved creator only
        "7407"            # skip granting creator bits for ordinary joiners
        "838bcc00000007"  # retain the creator's original flags
    )
    return code + jump(CAVE_RVA + len(code), RETURN_RVA)


def operations() -> tuple[tuple[int, bytes, bytes], ...]:
    code = authority_stub()
    return (
        # Stock K2 enters retained-record lookup only with a nonzero connection
        # ID. The authority stub supplies a private sentinel only for a route
        # the gateway has actually retired. First admissions therefore stay on
        # the untouched unique-allocation path. During that explicit reconnect,
        # accept a connectionless local record and compare its account below.
        (
            GENERATE_ID_RECONNECT_MARKER_RVA,
            bytes.fromhex("80780a007506"),
            bytes.fromhex("66833b7f7506"),
        ),
        (
            GENERATE_ID_COMPARE_RVA,
            bytes.fromhex("66395008"),
            bytes.fromhex("39680490"),
        ),
        # Enter the proven local constructor even for a creator-marked C0.
        (MARKER_REJECTION_RVA, bytes.fromhex("0f859a020000"), b"\x90" * 6),
        (HOOK_RVA, bytes.fromhex("838bcc00000007"), jump(HOOK_RVA, CAVE_RVA) + b"\x90\x90"),
        (CAVE_RVA, bytes(0x40), code.ljust(0x40, b"\0")),
        # AuthSuccess's legacy account/roster fallback must not override the
        # master decision. Host-flag testing and NETCMD_GAME_HOST stay native.
        (PROMOTION_RVA, bytes.fromhex("838dcc00000001"), b"\x90" * 7),
        # The local admission branch used to overwrite the parsed identity
        # immediately before GenerateClientID/CPlayer initialization.
        (ACCOUNT_RESET_RVA, bytes.fromhex("897d0c"), b"\x90" * 3),
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
