"""Build the ThorGor v64 linked-client state-block fix from verified k2.v57.

The v57 input is the verified ThorGor interoperability build.  v64 keeps the
v63 all-client state-string delivery and routes state-block broadcasts through
a narrow wrapper that accepts an active linked client even while its transient
client-number field is -1 during the picking-phase transition.
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path


SOURCE_SHA256 = "6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF"
OUTPUT_SHA256 = "570BFB5A9AE90AAACDAEBEBCCA2BE0572DC631D7211AC889226A4DF7359CF043"

SET_BLOCK_HOOK = 0x2F26C4
SET_BLOCK_RETURN = 0x2F26DB
QUEUE_BLOCK = 0x2F75D0
QUEUE_BLOCK_BODY = 0x2F75F2
QUEUE_BLOCK_EPILOGUE = 0x2F76EA
QUEUE_STRING = 0x2F7700
BLOCK_CAVE = 0x70D600
STRING_CAVE = 0x70D640
BLOCK_QUEUE_WRAPPER = 0x70D680
STRING_CALLS = (0x2F3B51, 0x2F3BE7, 0x2F3C84, 0x2F3D24)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def rel32(instruction_rva: int, target_rva: int) -> bytes:
    return struct.pack("<i", target_rva - (instruction_rva + 5))


def rel32_6(instruction_rva: int, target_rva: int) -> bytes:
    return struct.pack("<i", target_rva - (instruction_rva + 6))


def call(instruction_rva: int, target_rva: int) -> bytes:
    return b"\xE8" + rel32(instruction_rva, target_rva)


def jump(instruction_rva: int, target_rva: int) -> bytes:
    return b"\xE9" + rel32(instruction_rva, target_rva)


def jz(instruction_rva: int, target_rva: int) -> bytes:
    return b"\x0F\x84" + rel32_6(instruction_rva, target_rva)


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
    require(data, SET_BLOCK_HOOK, original_set_tail, "SetStateBlock tail")
    for site in STRING_CALLS:
        require(data, site, call(site, QUEUE_STRING), "UpdateStateStrings call")
    require(data, BLOCK_CAVE, b"\0" * 0xC0, "v64 code cave")

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

    # Preserve QueueStateBlock's prologue and active-connection check at
    # client+0x8228, then enter just after its transient client-number guard.
    # Its own epilogue returns normally to the broadcast loop.
    block_queue_wrapper = bytearray.fromhex(
        "51"                # push ecx
        "53"                # push ebx
        "55"                # push ebp
        "8b6c2410"          # mov ebp,[esp+0x10] (client)
        "83bd2882000000"    # cmp dword ptr [ebp+0x8228],0
        "56"                # push esi
        "57"                # push edi
        "8bf8"              # mov edi,eax (state block)
    )
    block_queue_wrapper += jz(
        BLOCK_QUEUE_WRAPPER + len(block_queue_wrapper), QUEUE_BLOCK_EPILOGUE
    )
    block_queue_wrapper += jump(
        BLOCK_QUEUE_WRAPPER + len(block_queue_wrapper), QUEUE_BLOCK_BODY
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
    data[SET_BLOCK_HOOK : SET_BLOCK_HOOK + len(original_set_tail)] = (
        jump(SET_BLOCK_HOOK, BLOCK_CAVE)
        + b"\x90" * (len(original_set_tail) - 5)
    )
    for site in STRING_CALLS:
        data[site : site + 5] = call(site, STRING_CAVE)

    result = sha256(data)
    if OUTPUT_SHA256 and result != OUTPUT_SHA256:
        raise ValueError(f"unexpected v64 output hash {result}")
    target.write_bytes(data)
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: build_k2_v64.py K2_V57_DLL OUTPUT_K2_DLL", file=sys.stderr)
        return 2
    try:
        print(build(Path(argv[1]), Path(argv[2])))
    except (OSError, ValueError) as exc:
        print(f"patch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
