"""Atomically transfer a retained CPlayer to K2's fresh reconnect number.

K2 must keep its stock fresh-allocation path.  Reusing a still-registered K2
transport number crashes the slave before game.dll sees the reconnect.  Once
game.dll has matched the retained player by authenticated account identity,
this patch rekeys IGame's native ``map<int, CPlayer *>`` with the game's own
erase and insert primitives, then updates CPlayer::clientNumber.
"""
from __future__ import annotations

import struct
from pathlib import Path

from thorgor.patches.engine import _rva_to_file, sha256

SOURCE_SHA256 = "929FADD55C141946BC102704C06F41A4AAB74ABE1CC92DFE2E185C5A3B88C35B"
OUTPUT_SHA256 = "EDE947C89F2503612A5CC8835AD730DBC99D4F9D958ADA4A96129D9A58BED856"

HOOK_RVA = 0x333DD
SUCCESS_RVA = 0x333FB
CAVE_RVA = 0x73B00
CAVE_SIZE = 0x100

ITERATOR_NEXT_RVA = 0x1B1C0
ERASE_RANGE_RVA = 0x161B0
MAP_INDEX_RVA = 0x04130


def relative(opcode: int, source: int, target: int) -> bytes:
    return bytes((opcode,)) + struct.pack("<i", target - source - 5)


def reconnect_stub() -> bytes:
    code = bytearray()

    def emit(value: bytes) -> None:
        code.extend(value)

    def call(target: int) -> None:
        emit(relative(0xE8, CAVE_RVA + len(code), target))

    def jump(target: int) -> None:
        emit(relative(0xE9, CAVE_RVA + len(code), target))

    emit(bytes.fromhex("8B5708"))          # edx = connection->clientNumber
    emit(bytes.fromhex("39506C"))          # retained number already matches?
    same_number_branch = len(code)
    emit(b"\x0f\x84\0\0\0\0")          # je same-number tail

    emit(b"\x60")                         # preserve reconnect function state
    emit(bytes.fromhex("83EC10"))          # result, first, last, new key
    emit(bytes.fromhex("8B542420"))        # first = retained map node (saved ebx)
    emit(bytes.fromhex("89542404"))
    emit(bytes.fromhex("89542408"))        # last starts at retained node
    emit(bytes.fromhex("8D542408"))        # native iterator++(&last)
    call(ITERATOR_NEXT_RVA)

    emit(bytes.fromhex("8B7C2418"))        # edi = original frame
    emit(bytes.fromhex("8B7F08"))          # edi = IGame
    emit(bytes.fromhex("81C7FC000000"))    # edi = &IGame::playerMap
    emit(bytes.fromhex("8D0424"))          # range erase result storage
    emit(bytes.fromhex("FF742408"))        # push last
    emit(bytes.fromhex("FF742408"))        # push first (offset shifted)
    emit(b"\x50")                         # push result; callee pops 12
    call(ERASE_RANGE_RVA)

    emit(bytes.fromhex("8B4C2410"))        # original connection (saved edi)
    emit(bytes.fromhex("8B5108"))          # authoritative fresh number
    emit(bytes.fromhex("8954240C"))        # new map key
    emit(bytes.fromhex("8D74240C"))        # map operator[] key ABI: esi
    emit(bytes.fromhex("89F9"))            # map operator[] this ABI: ecx
    call(MAP_INDEX_RVA)
    emit(bytes.fromhex("8B54242C"))        # retained player (saved eax)
    emit(bytes.fromhex("8910"))            # new map value = retained player
    emit(bytes.fromhex("8B4C240C"))
    emit(bytes.fromhex("894A6C"))          # player->clientNumber = new key
    emit(bytes.fromhex("83C410"))
    emit(b"\x61")                         # restore caller state
    emit(bytes.fromhex("8B4708"))          # match stock success register state
    jump(SUCCESS_RVA)

    same_number_tail = len(code)
    emit(bytes.fromhex("89D0"))            # eax = matching client number
    jump(SUCCESS_RVA)

    displacement = same_number_tail - (same_number_branch + 6)
    struct.pack_into("<i", code, same_number_branch + 2, displacement)
    if len(code) > CAVE_SIZE:
        raise ValueError("reconnect transfer stub exceeds its verified code cave")
    return bytes(code)


def operations() -> tuple[tuple[int, bytes, bytes], ...]:
    stub = reconnect_stub()
    return (
        (
            HOOK_RVA,
            bytes.fromhex("8B406C3B47087416"),
            relative(0xE9, HOOK_RVA, CAVE_RVA) + b"\x90\x90\x90",
        ),
        (CAVE_RVA, bytes(CAVE_SIZE), stub.ljust(CAVE_SIZE, b"\0")),
    )


def build(source: Path, target: Path) -> str:
    data = bytearray(source.read_bytes())
    if sha256(data) != SOURCE_SHA256:
        raise ValueError("reconnect identity transfer requires the capacity-patched game.dll")
    for rva, expected, replacement in operations():
        offset = _rva_to_file(data, rva)
        if data[offset:offset + len(expected)] != expected:
            raise ValueError(f"unexpected reconnect patch bytes at RVA 0x{rva:X}")
        data[offset:offset + len(replacement)] = replacement
    digest = sha256(data)
    if digest != OUTPUT_SHA256:
        raise ValueError(f"unexpected reconnect identity output hash {digest}")
    target.write_bytes(data)
    return digest
