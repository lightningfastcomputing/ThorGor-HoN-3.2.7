"""Build the v36 host-migration fallback for a reconnected successor.

Retail host migration resolves the candidate CPlayer and then asks K2 for a
CClientConnection by the player's fresh live client number.  After reconnect,
the retained player is valid and receiving traffic, but that K2 lookup can
still return null because its registry remains keyed by the historical
allocation.  In that one case, promote the already-validated game-side player
without dereferencing a null CClientConnection.  The normal non-null path is
returned to stock code unchanged.
"""
from __future__ import annotations

import struct


HOOK_RVA = 0x32FE1
HOOK_SIZE = 8
BASE_RVA = 0x73DB0
ITERATE_RVA = 0x3305F
STOCK_CONNECTION_RVA = 0x32FE9
PROMOTE_WITHOUT_CONNECTION_RVA = 0x33001


class Assembler:
    def __init__(self, base: int):
        self.base = base
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, int, str | int]] = []

    def emit(self, data: str) -> None:
        self.code.extend(bytes.fromhex(data))

    def label(self, name: str) -> None:
        self.labels[name] = self.base + len(self.code)

    def relative(self, opcode: str, target: str | int) -> None:
        self.emit(opcode)
        position = len(self.code)
        self.code.extend(b"\0\0\0\0")
        self.fixups.append((position, self.base + position + 4, target))

    def finish(self) -> bytes:
        for position, next_address, target in self.fixups:
            destination = self.labels[target] if isinstance(target, str) else target
            self.code[position:position + 4] = struct.pack("<i", destination - next_address)
        return bytes(self.code)


def build() -> bytes:
    asm = Assembler(BASE_RVA)
    asm.emit("85C0")                 # stock GetClient result is non-null
    asm.relative("0F85", "stock_connection")

    # Null K2 lookup: v35 has already resolved EBX to the iterated retained
    # CPlayer.  Retain stock rejection for a missing player or invalid live ID.
    asm.emit("85DB")
    asm.relative("0F84", ITERATE_RVA)
    asm.emit("8B4E10")               # ecx = iterated CPlayer
    asm.emit("83796CFF")             # CPlayer+0x6c != -1
    asm.relative("0F84", ITERATE_RVA)
    asm.emit("66838B5A03000004")     # mark game-side host on the CPlayer
    asm.relative("E9", PROMOTE_WITHOUT_CONNECTION_RVA)

    asm.label("stock_connection")
    asm.emit("85DB")                 # displaced stock player guard
    asm.relative("0F84", ITERATE_RVA)
    asm.relative("E9", STOCK_CONNECTION_RVA)
    return asm.finish()


def hook() -> bytes:
    next_rva = HOOK_RVA + 5
    return b"\xE9" + struct.pack("<i", BASE_RVA - next_rva) + b"\x90" * (HOOK_SIZE - 5)


if __name__ == "__main__":
    stub = build()
    print(f"hook={hook().hex().upper()}")
    print(f"length={len(stub)}")
    print(stub.hex().upper())
