"""Build the ThorGor v66 per-client state reconciliation fix from k2.v57.

The v57 input is the verified ThorGor interoperability build. v66 keeps the
all-client delivery work and replaces the periodic first-client-only state-block
revision check with a true per-client reconciliation loop.
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path


SOURCE_SHA256 = "6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF"
OUTPUT_SHA256 = "2BC131F1C40D9F84CAD288426B14B0DB1EE58E43FC64DB86FF5AEFFC82D58657"

SET_BLOCK_HOOK = 0x2F26C4
SET_BLOCK_RETURN = 0x2F26DB
QUEUE_BLOCK = 0x2F75D0
QUEUE_BLOCK_BODY = 0x2F75F2
QUEUE_STRING = 0x2F7700
BLOCK_CAVE = 0x70D600
STRING_CAVE = 0x70D640
BLOCK_QUEUE_WRAPPER = 0x70D680
PERIODIC_BLOCK_START = 0x2F3DAF
PERIODIC_BLOCK_RETURN = 0x2F3E02
RECONCILE_WRAPPER = 0x70D6C0
STRING_CALLS = (0x2F3B51, 0x2F3BE7, 0x2F3C84, 0x2F3D24)


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
        raise ValueError(f"unexpected v57 source hash {digest}")

    original_set_tail = bytes.fromhex(
        "8bb68001000085f6740d8b44241450568bc3e8f54e0000"
    )
    original_periodic_block = bytes.fromhex(
        "8b878001000085c074498b905c83000085d2750433c9eb0b"
        "8b88608300002bcac1f9023bd9720583c9ffeb038b0c9a39"
        "4e18741f8b4dec51508bc6e8e1370000807f0400740d8b97"
        "980000005653ffd283c408"
    )
    require(data, SET_BLOCK_HOOK, original_set_tail, "SetStateBlock tail")
    for site in STRING_CALLS:
        require(data, site, call(site, QUEUE_STRING), "UpdateStateStrings call")
    require(data, BLOCK_CAVE, b"\0" * 0xC0, "v66 primary code cave")
    require(
        data,
        PERIODIC_BLOCK_START,
        original_periodic_block,
        "periodic first-client state-block reconciliation",
    )
    require(data, RECONCILE_WRAPPER, b"\0" * 0x80, "v66 reconciliation cave")

    # Walk every linked client for a dynamic state-block update. The normal
    # helper is retained for all other callers; this path uses the scoped
    # wrapper below so a joined client is not filtered during phase changes.
    block_stub = bytearray.fromhex(
        "8bb680010000"      # mov esi,[esi+0x180]
        "85f6"              # test esi,esi
        "7417"              # jz done
        "8b442414"          # loop: mov eax,[esp+0x14]
        "50"                # push eax (state block ID)
        "56"                # push esi (client)
        "8bc3"              # mov eax,ebx (state block)
    )
    block_stub += call(BLOCK_CAVE + len(block_stub), BLOCK_QUEUE_WRAPPER)
    block_stub += bytes.fromhex(
        "8bb630840000"      # mov esi,[esi+0x8430]
        "85f6"              # test esi,esi
        "75e9"              # jnz loop
    )
    block_stub += jump(BLOCK_CAVE + len(block_stub), SET_BLOCK_RETURN)

    # Reproduce QueueStateBlock's prologue, then enter after its two stale
    # readiness filters. Membership in the host's linked-client list is the
    # recipient authority for this broadcast-only path. The original helper
    # and both filters remain unchanged for admission and targeted sends.
    block_queue_wrapper = bytearray.fromhex(
        "51"                # push ecx
        "53"                # push ebx
        "55"                # push ebp
        "8b6c2410"          # mov ebp,[esp+0x10] (client)
        "56"                # push esi
        "57"                # push edi
        "8bf8"              # mov edi,eax (state block)
    )
    block_queue_wrapper += jump(
        BLOCK_QUEUE_WRAPPER + len(block_queue_wrapper), QUEUE_BLOCK_BODY
    )

    # UpdateStateStrings historically compared each host state-block revision
    # against only the list head. Compare and queue independently for every
    # linked client so an up-to-date host cannot hide a stale joined client.
    reconcile = bytearray.fromhex(
        "60"                # pushad
        "8bbf80010000"      # mov edi,[edi+0x180] (client head)
    )
    loop_rva = RECONCILE_WRAPPER + len(reconcile)
    reconcile += bytes.fromhex("85ff")  # test edi,edi
    done_jz = RECONCILE_WRAPPER + len(reconcile)
    reconcile += b"\x0f\x84\0\0\0\0"
    reconcile += bytes.fromhex("83bf2882000000")  # cmp [edi+0x8228],0
    inactive_jz = RECONCILE_WRAPPER + len(reconcile)
    reconcile += b"\x0f\x84\0\0\0\0"
    reconcile += bytes.fromhex(
        "8b975c830000"      # mov edx,[edi+0x835c] (revision vector begin)
        "85d2"              # test edx,edx
    )
    null_jz = RECONCILE_WRAPPER + len(reconcile)
    reconcile += b"\x0f\x84\0\0\0\0"
    reconcile += bytes.fromhex(
        "8b8f60830000"      # mov ecx,[edi+0x8360] (revision vector end)
        "2bca"              # sub ecx,edx
        "c1f902"            # sar ecx,2
        "3bd9"              # cmp ebx,ecx
    )
    range_jae = RECONCILE_WRAPPER + len(reconcile)
    reconcile += b"\x0f\x83\0\0\0\0"
    reconcile += bytes.fromhex(
        "8b0c9a"            # mov ecx,[edx+ebx*4]
        "394e18"            # cmp [esi+0x18],ecx (host vs client revision)
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
    reconcile += call(RECONCILE_WRAPPER + len(reconcile), BLOCK_QUEUE_WRAPPER)
    next_rva = RECONCILE_WRAPPER + len(reconcile)
    reconcile += bytes.fromhex("8bbf30840000")  # mov edi,[edi+0x8430]
    reconcile += jump(RECONCILE_WRAPPER + len(reconcile), loop_rva)
    done_rva = RECONCILE_WRAPPER + len(reconcile)
    reconcile += bytes.fromhex("61c3")  # popad; ret

    reconcile[done_jz - RECONCILE_WRAPPER : done_jz - RECONCILE_WRAPPER + 6] = jcc(
        done_jz, done_rva, 0x84
    )
    reconcile[
        inactive_jz - RECONCILE_WRAPPER : inactive_jz - RECONCILE_WRAPPER + 6
    ] = jcc(inactive_jz, next_rva, 0x84)
    reconcile[null_jz - RECONCILE_WRAPPER : null_jz - RECONCILE_WRAPPER + 6] = jcc(
        null_jz, queue_rva, 0x84
    )
    reconcile[range_jae - RECONCILE_WRAPPER : range_jae - RECONCILE_WRAPPER + 6] = jcc(
        range_jae, queue_rva, 0x83
    )
    reconcile[current_je - RECONCILE_WRAPPER : current_je - RECONCILE_WRAPPER + 6] = jcc(
        current_je, next_rva, 0x84
    )

    # Preserve v63 state-string delivery for all linked clients.
    string_stub = bytearray.fromhex(
        "535657"            # push ebx; push esi; push edi
        "8bd8"              # mov ebx,eax (state-string delta)
        "8bf9"              # mov edi,ecx (state-string ID)
        "8b742410"          # mov esi,[esp+0x10] (head client)
        "85f6"              # test esi,esi
        "7414"              # jz done
        "56"                # loop: push esi
        "8bc3"              # mov eax,ebx
        "8bcf"              # mov ecx,edi
    )
    string_stub += call(STRING_CAVE + len(string_stub), QUEUE_STRING)
    string_stub += bytes.fromhex(
        "8bb630840000"      # mov esi,[esi+0x8430]
        "85f6"              # test esi,esi
        "75ec"              # jnz loop
        "5f5e5b"            # pop edi; pop esi; pop ebx
        "c20400"            # ret 4
    )

    data[BLOCK_CAVE : BLOCK_CAVE + len(block_stub)] = block_stub
    data[STRING_CAVE : STRING_CAVE + len(string_stub)] = string_stub
    data[
        BLOCK_QUEUE_WRAPPER : BLOCK_QUEUE_WRAPPER + len(block_queue_wrapper)
    ] = block_queue_wrapper
    data[RECONCILE_WRAPPER : RECONCILE_WRAPPER + len(reconcile)] = reconcile
    data[SET_BLOCK_HOOK : SET_BLOCK_HOOK + len(original_set_tail)] = (
        jump(SET_BLOCK_HOOK, BLOCK_CAVE)
        + b"\x90" * (len(original_set_tail) - 5)
    )
    for site in STRING_CALLS:
        data[site : site + 5] = call(site, STRING_CAVE)
    data[PERIODIC_BLOCK_START:PERIODIC_BLOCK_RETURN] = (
        call(PERIODIC_BLOCK_START, RECONCILE_WRAPPER)
        + b"\x90" * (len(original_periodic_block) - 5)
    )

    result = sha256(data)
    if OUTPUT_SHA256 and result != OUTPUT_SHA256:
        raise ValueError(f"unexpected v66 output hash {result}")
    target.write_bytes(data)
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: build_k2_v66.py K2_V57_DLL OUTPUT_K2_DLL", file=sys.stderr)
        return 2
    try:
        print(build(Path(argv[1]), Path(argv[2])))
    except (OSError, ValueError) as exc:
        print(f"patch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
