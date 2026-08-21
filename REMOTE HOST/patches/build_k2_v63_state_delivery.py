"""Build the ThorGor v63 state-delivery fix from a verified k2.v57.dll.

The v57 input is already the verified ThorGor interoperability build.  This
output changes only the two dynamic state queue paths that previously queued
updates for the head client instead of walking the linked client list.
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path


SOURCE_SHA256 = "6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF"
OUTPUT_SHA256 = "9C3D512ACFF549ACBF82A0A46A59D64C6F0F06AD26C831F0DAB7F10A793ED885"

SET_BLOCK_HOOK = 0x2F26C4
SET_BLOCK_RETURN = 0x2F26DB
QUEUE_BLOCK = 0x2F75D0
QUEUE_STRING = 0x2F7700
BLOCK_CAVE = 0x70D600
STRING_CAVE = 0x70D640
STRING_CALLS = (0x2F3B51, 0x2F3BE7, 0x2F3C84, 0x2F3D24)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def rel32(instruction_rva: int, target_rva: int) -> bytes:
    return struct.pack("<i", target_rva - (instruction_rva + 5))


def call(instruction_rva: int, target_rva: int) -> bytes:
    return b"\xE8" + rel32(instruction_rva, target_rva)


def jump(instruction_rva: int, target_rva: int) -> bytes:
    return b"\xE9" + rel32(instruction_rva, target_rva)


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
    require(data, BLOCK_CAVE, b"\0" * 0x80, "v63 code cave")

    # CHostServer::SetStateBlock tail. ESI is the host, EBX is the state block,
    # and [ESP+0x14] is its ID. Queue it for every linked client, then return to
    # the original epilogue. CClientConnection::next is +0x8430 in v57.
    block_stub = bytearray.fromhex(
        "8bb680010000"      # mov esi,[esi+0x180]
        "85f6"              # test esi,esi
        "7417"              # jz done
        "8b442414"          # loop: mov eax,[esp+0x14]
        "50"                # push eax (state block ID)
        "56"                # push esi (client)
        "8bc3"              # mov eax,ebx (state block)
    )
    block_stub += call(BLOCK_CAVE + len(block_stub), QUEUE_BLOCK)
    block_stub += bytes.fromhex(
        "8bb630840000"      # mov esi,[esi+0x8430]
        "85f6"              # test esi,esi
        "75e9"              # jnz loop
    )
    block_stub += jump(BLOCK_CAVE + len(block_stub), SET_BLOCK_RETURN)

    # Wrapper for the existing state-string queue helper. It preserves the
    # helper's EAX/ECX/stack calling convention while substituting each linked
    # client in turn, and returns with the original four-byte stack cleanup.
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
    data[SET_BLOCK_HOOK : SET_BLOCK_HOOK + len(original_set_tail)] = (
        jump(SET_BLOCK_HOOK, BLOCK_CAVE)
        + b"\x90" * (len(original_set_tail) - 5)
    )
    for site in STRING_CALLS:
        data[site : site + 5] = call(site, STRING_CAVE)

    result = sha256(data)
    if OUTPUT_SHA256 and result != OUTPUT_SHA256:
        raise ValueError(f"unexpected v63 output hash {result}")
    target.write_bytes(data)
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: build_k2_v63.py K2_V57_DLL OUTPUT_K2_DLL", file=sys.stderr)
        return 2
    try:
        print(build(Path(argv[1]), Path(argv[2])))
    except (OSError, ValueError) as exc:
        print(f"patch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
