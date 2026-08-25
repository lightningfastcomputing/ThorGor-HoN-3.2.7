"""Build ThorGor K2 v76 from the verified stable v65 DLL.

The game updates hero-list state blocks 3 through 8 by modifying their buffers
directly.  That bypasses v65's immediate SetStateBlock broadcast hook.  K2's
periodic revision reconciliation historically checks only the first linked
client, so an up-to-date host can hide a stale joiner.

v76 replaces only that periodic check.  It compares blocks 3..8 independently
for every fully world-loaded linked client and calls K2's original guarded
QueueStateBlock entry point.  The world-loaded gate prevents state changes from
being queued during initial admission, when doing so can poison the first
snapshot.  The original call both queues the block and advances that client's
server-side state sequence, keeping subsequent snapshots synchronized.
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path


SOURCE_SHA256 = "82D0363C0BC853ECD60A3AD8A62E01E2BF0897EB1644364FBAC82C7E2B48ECAB"
OUTPUT_SHA256 = "FF25B3EF1D3CCB5F8EE765A036AD6EF6DB984096AAE1E0E97594EDF51A3A3AC0"

QUEUE_BLOCK = 0x2F75D0
PERIODIC_BLOCK_START = 0x2F3DAF
PERIODIC_BLOCK_RETURN = 0x2F3E02
RECONCILE_WRAPPER = 0x70D6C0


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

    original_periodic_block = bytes.fromhex(
        "8b878001000085c074498b905c83000085d2750433c9eb0b"
        "8b88608300002bcac1f9023bd9720583c9ffeb038b0c9a39"
        "4e18741f8b4dec51508bc6e8e1370000807f0400740d8b97"
        "980000005653ffd283c408"
    )
    require(
        data,
        PERIODIC_BLOCK_START,
        original_periodic_block,
        "periodic first-client state-block reconciliation",
    )
    require(data, RECONCILE_WRAPPER, b"\0" * 0x80, "v76 reconciliation cave")

    reconcile = bytearray.fromhex(
        "60"                # pushad
        "8d43fd"            # lea eax,[ebx-3]
        "83f805"            # cmp eax,5 (accept original EBX 3..8)
    )
    above_guard = RECONCILE_WRAPPER + len(reconcile)
    reconcile += b"\x0f\x87\0\0\0\0"  # ja done
    reconcile += bytes.fromhex(
        "8bbf80010000"      # mov edi,[edi+0x180] (client head)
    )
    loop_rva = RECONCILE_WRAPPER + len(reconcile)
    reconcile += bytes.fromhex("85ff")  # test edi,edi
    done_jz = RECONCILE_WRAPPER + len(reconcile)
    reconcile += b"\x0f\x84\0\0\0\0"
    reconcile += bytes.fromhex("83bf2882000000")  # cmp [edi+0x8228],0
    inactive_jz = RECONCILE_WRAPPER + len(reconcile)
    reconcile += b"\x0f\x84\0\0\0\0"
    reconcile += bytes.fromhex("80bf3682000001")  # cmp byte [edi+0x8236],1 (world loaded)
    not_loaded_jne = RECONCILE_WRAPPER + len(reconcile)
    reconcile += b"\x0f\x85\0\0\0\0"
    reconcile += bytes.fromhex(
        "8b975c830000"      # mov edx,[edi+0x835c] (revision begin)
        "85d2"              # test edx,edx
    )
    null_jz = RECONCILE_WRAPPER + len(reconcile)
    reconcile += b"\x0f\x84\0\0\0\0"
    reconcile += bytes.fromhex(
        "8b8f60830000"      # mov ecx,[edi+0x8360] (revision end)
        "2bca"              # sub ecx,edx
        "c1f902"            # sar ecx,2
        "3bd9"              # cmp ebx,ecx
    )
    range_jae = RECONCILE_WRAPPER + len(reconcile)
    reconcile += b"\x0f\x83\0\0\0\0"
    reconcile += bytes.fromhex(
        "8b0c9a"            # mov ecx,[edx+ebx*4]
        "394e18"            # cmp [esi+0x18],ecx (host/client revision)
    )
    current_je = RECONCILE_WRAPPER + len(reconcile)
    reconcile += b"\x0f\x84\0\0\0\0"
    queue_rva = RECONCILE_WRAPPER + len(reconcile)
    reconcile += bytes.fromhex(
        "8b4dec"            # mov ecx,[ebp-0x14] (state-block ID)
        "51"                # push ecx
        "57"                # push edi (client)
        "8bc6"              # mov eax,esi (state block)
    )
    reconcile += call(RECONCILE_WRAPPER + len(reconcile), QUEUE_BLOCK)
    next_rva = RECONCILE_WRAPPER + len(reconcile)
    reconcile += bytes.fromhex("8bbf30840000")  # mov edi,[edi+0x8430]
    reconcile += jump(RECONCILE_WRAPPER + len(reconcile), loop_rva)
    done_rva = RECONCILE_WRAPPER + len(reconcile)
    reconcile += bytes.fromhex("61c3")  # popad; ret

    for site, condition in ((above_guard, 0x87), (done_jz, 0x84)):
        start = site - RECONCILE_WRAPPER
        reconcile[start : start + 6] = jcc(site, done_rva, condition)
    for site in (inactive_jz, current_je):
        start = site - RECONCILE_WRAPPER
        reconcile[start : start + 6] = jcc(site, next_rva, 0x84)
    start = not_loaded_jne - RECONCILE_WRAPPER
    reconcile[start : start + 6] = jcc(not_loaded_jne, next_rva, 0x85)
    for site, condition in ((null_jz, 0x84), (range_jae, 0x83)):
        start = site - RECONCILE_WRAPPER
        reconcile[start : start + 6] = jcc(site, queue_rva, condition)

    if len(reconcile) > 0x80:
        raise ValueError(f"v76 reconciliation stub is too large: {len(reconcile)}")

    data[RECONCILE_WRAPPER : RECONCILE_WRAPPER + len(reconcile)] = reconcile
    data[PERIODIC_BLOCK_START:PERIODIC_BLOCK_RETURN] = (
        call(PERIODIC_BLOCK_START, RECONCILE_WRAPPER)
        + b"\x90" * (len(original_periodic_block) - 5)
    )

    result = sha256(data)
    if OUTPUT_SHA256 and result != OUTPUT_SHA256:
        raise ValueError(f"unexpected output hash {result}")
    target.write_bytes(data)
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: build_k2_v76.py K2_V65_DLL OUTPUT_K2_DLL", file=sys.stderr)
        return 2
    try:
        print(build(Path(argv[1]), Path(argv[2])))
    except (OSError, ValueError) as exc:
        print(f"patch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
