"""Build the isolated game-command player lookup fallback used by reconnect v29."""
from __future__ import annotations

import struct


BASE_RVA = 0x73B00
STOCK_HIT_RVA = 0x47915
STOCK_MISS_RVA = 0x4790E


class Assembler:
    def __init__(self, base: int):
        self.base = base
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, int, str]] = []

    def emit(self, data: str) -> None:
        self.code.extend(bytes.fromhex(data))

    def label(self, name: str) -> None:
        self.labels[name] = self.base + len(self.code)

    def branch(self, opcode: str, target: str) -> None:
        self.emit(opcode)
        position = len(self.code)
        self.code.extend(b"\0\0\0\0")
        self.fixups.append((position, self.base + position + 4, target))

    def finish(self) -> bytes:
        for position, next_address, target in self.fixups:
            destination = self.labels[target]
            self.code[position:position + 4] = struct.pack("<i", destination - next_address)
        return bytes(self.code)


def build() -> bytes:
    asm = Assembler(BASE_RVA)
    asm.emit("8B4D30")             # ecx = stock lookup result node
    asm.emit("3BC8")               # stock result != head means a normal hit
    asm.branch("0F85", "hit")
    asm.emit("8BD0")               # edx = tree head/sentinel
    asm.emit("8B08")               # ecx = leftmost node
    asm.emit("3BCA")
    asm.branch("0F84", "miss")

    asm.label("scan")
    asm.emit("8B7910")             # edi = retained CPlayer value
    asm.emit("85FF")
    asm.branch("0F84", "advance")
    asm.emit("8B5F6C")             # ebx = retained player's live client number
    asm.emit("3B5D44")             # compare with packet sender client number
    asm.branch("0F84", "hit")

    asm.label("advance")
    asm.emit("8B7908")             # try the right subtree
    asm.emit("3BFA")
    asm.branch("0F84", "parents")
    asm.emit("8BCF")

    asm.label("leftmost")
    asm.emit("8B39")
    asm.emit("3BFA")
    asm.branch("0F84", "scan")
    asm.emit("8BCF")
    asm.branch("E9", "leftmost")

    asm.label("parents")
    asm.emit("8B7904")
    asm.emit("3BFA")
    asm.branch("0F84", "miss")
    asm.emit("3B4F08")
    asm.branch("0F85", "use_parent")
    asm.emit("8BCF")
    asm.branch("E9", "parents")

    asm.label("use_parent")
    asm.emit("8BCF")
    asm.branch("E9", "scan")

    asm.label("hit")
    asm.labels["stock_hit"] = STOCK_HIT_RVA
    asm.branch("E9", "stock_hit")
    asm.label("miss")
    asm.labels["stock_miss"] = STOCK_MISS_RVA
    asm.branch("E9", "stock_miss")
    return asm.finish()


if __name__ == "__main__":
    stub = build()
    print(f"length={len(stub)}")
    print(stub.hex().upper())
