"""Preserve the linked registry when a managed slave removes its head client.

This is a separate successor to frozen v39, never an edit of its builder.
The retail local-client destructor clears CHostServer+180. ThorGor's linked
transport loops use that field as their only registry root. Save the successor
before freeing the departing head and retain it only on manager-owned slaves.
"""
from __future__ import annotations

import struct
from pathlib import Path

from thorgor.patches.engine import _rva_to_file, sha256


SOURCE_SHA256 = "CB12258566BA001B528F3A48E4C8CC795992DCB17333BCE5ABF8EF4E5DCCB24D"
OUTPUT_SHA256 = "98138B1086092558014B4808D3AA75B00BA87450EA3112171F68CC3DC99048C2"
HOOK_RVA = 0x2F2E4A
CAVE_RVA = 0x70D800
RETURN_RVA = 0x2F2E61
FREE_RVA = 0x474F0


def branch(opcode, source, target):
    return bytes([opcode]) + struct.pack("<i", target - source - 5)


def stub():
    code = bytearray.fromhex(
        "8bb780010000"      # displaced mov esi,[edi+180]
        "80bfd002000000"    # cmp byte [edi+2d0],0
        "7505"              # managed: skip retail-path jump
    )
    code += branch(0xE9, CAVE_RVA + len(code), HOOK_RVA + 6)
    code += bytes.fromhex(
        "31db"              # ebx=0, as on the retail path
        "31ed"              # no successor if head is null
        "85f6"              # test esi,esi
        "7411"              # null: skip successor read and free
        "8bae30840000"      # ebp=head->next, before destructor
        "899e30840000"      # detach head from surviving chain
    )
    code += branch(0xE8, CAVE_RVA + len(code), FREE_RVA)
    code += bytes.fromhex("89af80010000")  # host->head=successor
    code += branch(0xE9, CAVE_RVA + len(code), RETURN_RVA)
    return bytes(code)


def build(source: Path, target: Path):
    data = bytearray(source.read_bytes())
    if sha256(data) != SOURCE_SHA256:
        raise ValueError("registry continuity requires frozen v39 K2")
    hook = _rva_to_file(data, HOOK_RVA)
    cave = _rva_to_file(data, CAVE_RVA)
    if data[hook:hook + 6] != bytes.fromhex("8bb780010000"):
        raise ValueError("unexpected managed client cleanup instructions")
    if any(data[cave:cave + 0x60]):
        raise ValueError("registry continuity cave is not empty")
    data[hook:hook + 6] = branch(0xE9, HOOK_RVA, CAVE_RVA) + b"\x90"
    code = stub()
    data[cave:cave + len(code)] = code
    digest = sha256(data)
    if digest != OUTPUT_SHA256:
        raise ValueError("unexpected registry-continuity output hash")
    target.write_bytes(data)
    return digest
