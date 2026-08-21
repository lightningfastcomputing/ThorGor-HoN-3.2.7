"""Build ThorGor K2 v77 from the verified stable v65 DLL.

The stock periodic state-block path queues a changed block only for the linked
list head, then invokes a required game-state callback.  Replacing that block
removed the callback and corrupted the first snapshot in v75/v76.

v77 preserves the original path byte-for-byte.  At its loop tail, after the
original head-client queue and callback have completed, a small addendum checks
only hero-list blocks 3..8 and queues a stale copy for each remaining linked
client through K2's original guarded QueueStateBlock function.
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path


SOURCE_SHA256 = "82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB"
OUTPUT_SHA256 = "25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026"

QUEUE_BLOCK = 0x2F75D0
TAIL_HOOK = 0x2F3E02
STATE_BLOCK_LOOP = 0x2F3D50
TAIL_WRAPPER = 0x70D6C0


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def rel32(instruction_rva: int, target_rva: int) -> bytes:
    return struct.pack("<i", target_rva - (instruction_rva + 5))


def call(instruction_rva: int, target_rva: int) -> bytes:
    return b"\xE8" + rel32(instruction_rva, target_rva)


def jump(instruction_rva: int, target_rva: int) -> bytes:
    return b"\xE9" + rel32(instruction_rva, target_rva)


def jcc(instruction_rva: int, target_rva: int, condition: int) -> bytes:
    return bytes((0x0F, condition)) + struct.pack(
        "<i", target_rva - (instruction_rva + 6)
    )


def jcc8(instruction_rva: int, target_rva: int, opcode: int) -> bytes:
    displacement = target_rva - (instruction_rva + 2)
    if not -128 <= displacement <= 127:
        raise ValueError("short conditional branch is out of range")
    return bytes((opcode, displacement & 0xFF))


def require(data: bytearray, offset: int, expected: bytes, label: str) -> None:
    actual = bytes(data[offset : offset + len(expected)])
    if actual != expected:
        raise ValueError(
            f"{label} byte mismatch at 0x{offset:X}: "
            f"expected {expected.hex()}, got {actual.hex()}"
        )


def build(source: Path, target: Path) -> str:
    data = bytearray(source.read_bytes())
    digest = sha256(data)
    if digest != SOURCE_SHA256:
        raise ValueError(f"unexpected v65 source hash {digest}")

    original_tail = bytes.fromhex("83c61ce946ffffff")
    require(data, TAIL_HOOK, original_tail, "state-block loop tail")
    require(data, TAIL_WRAPPER, b"\0" * 0x80, "v77 tail-recipient cave")

    stub = bytearray.fromhex(
        "60"                # pushad
        "8d43fd"            # lea eax,[ebx-3]
        "83f805"            # cmp eax,5 (accept original EBX 3..8)
    )
    range_ja = TAIL_WRAPPER + len(stub)
    stub += b"\x77\0"
    stub += bytes.fromhex(
        "8bbf80010000"      # mov edi,[edi+0x180] (client head)
        "85ff"              # test edi,edi
    )
    head_null_jz = TAIL_WRAPPER + len(stub)
    stub += b"\x74\0"
    stub += bytes.fromhex("8bbf30840000")  # mov edi,[edi+0x8430] (skip head)
    loop_rva = TAIL_WRAPPER + len(stub)
    stub += bytes.fromhex("85ff")
    done_jz = TAIL_WRAPPER + len(stub)
    stub += b"\x74\0"
    stub += bytes.fromhex("83bf2882000000")  # cmp [edi+0x8228],0
    inactive_jz = TAIL_WRAPPER + len(stub)
    stub += b"\x0f\x84\0\0\0\0"
    stub += bytes.fromhex(
        "8b975c830000"      # mov edx,[edi+0x835c] (revision begin)
        "85d2"
    )
    null_jz = TAIL_WRAPPER + len(stub)
    stub += b"\x0f\x84\0\0\0\0"
    stub += bytes.fromhex(
        "8b8f60830000"      # mov ecx,[edi+0x8360] (revision end)
        "2bca"
        "c1f902"
        "3bd9"
    )
    range_jae = TAIL_WRAPPER + len(stub)
    stub += b"\x0f\x83\0\0\0\0"
    stub += bytes.fromhex(
        "8b0c9a"            # mov ecx,[edx+ebx*4]
        "394e18"            # cmp [esi+0x18],ecx
    )
    current_je = TAIL_WRAPPER + len(stub)
    stub += b"\x0f\x84\0\0\0\0"
    queue_rva = TAIL_WRAPPER + len(stub)
    stub += bytes.fromhex(
        "8b4dec"            # mov ecx,[ebp-0x14] (state-block ID)
        "51"
        "57"
        "8bc6"              # mov eax,esi (state block)
    )
    stub += call(TAIL_WRAPPER + len(stub), QUEUE_BLOCK)
    next_rva = TAIL_WRAPPER + len(stub)
    stub += bytes.fromhex("8bbf30840000")
    stub += jump(TAIL_WRAPPER + len(stub), loop_rva)
    done_rva = TAIL_WRAPPER + len(stub)
    stub += bytes.fromhex("6183c61c")  # popad; original add esi,0x1c
    stub += jump(TAIL_WRAPPER + len(stub), STATE_BLOCK_LOOP)

    for site in (range_ja, head_null_jz, done_jz):
        opcode = 0x77 if site == range_ja else 0x74
        start = site - TAIL_WRAPPER
        stub[start : start + 2] = jcc8(site, done_rva, opcode)
    for site in (inactive_jz, current_je):
        start = site - TAIL_WRAPPER
        stub[start : start + 6] = jcc(site, next_rva, 0x84)
    for site, condition in ((null_jz, 0x84), (range_jae, 0x83)):
        start = site - TAIL_WRAPPER
        stub[start : start + 6] = jcc(site, queue_rva, condition)

    if len(stub) > 0x80:
        raise ValueError(f"v77 tail-recipient stub is too large: {len(stub)}")

    data[TAIL_WRAPPER : TAIL_WRAPPER + len(stub)] = stub
    data[TAIL_HOOK : TAIL_HOOK + len(original_tail)] = (
        jump(TAIL_HOOK, TAIL_WRAPPER) + b"\x90" * 3
    )

    result = sha256(data)
    if OUTPUT_SHA256 and result != OUTPUT_SHA256:
        raise ValueError(f"unexpected output hash {result}")
    target.write_bytes(data)
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: build_k2_v77.py K2_V65_DLL OUTPUT_K2_DLL", file=sys.stderr)
        return 2
    try:
        print(build(Path(argv[1]), Path(argv[2])))
    except (OSError, ValueError) as exc:
        print(f"patch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
