"""Build the v32 ProcessClientSnapshot reconnect lookup fallback."""
from __future__ import annotations

import struct


BASE_RVA = 0x73D00
FOUND_RVA = 0x2DD7A
NOT_FOUND_RVA = 0x2DD39


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
    asm.emit("85C9")                 # preserve a successful stock lookup
    asm.relative("0F85", "found")
    asm.emit("8BD6")                 # edx = map head
    asm.emit("8B0E")                 # ecx = first node

    asm.label("inspect")
    asm.emit("3BCA")                 # exhausted at map head
    asm.relative("0F84", "not_found")
    asm.emit("8B4110")               # eax = retained CPlayer value
    asm.emit("85C0")
    asm.relative("0F84", "next")
    asm.emit("39786C")               # CPlayer+0x6c == packet client number (edi)
    asm.relative("0F84", "found_player")

    asm.label("next")
    asm.emit("8B4108")               # follow right subtree when present
    asm.emit("3BC2")
    asm.relative("0F84", "ascend_start")
    asm.emit("8BC8")
    asm.label("descend")
    asm.emit("8B01")                 # descend to its leftmost node
    asm.emit("3BC2")
    asm.relative("0F84", "inspect")
    asm.emit("8BC8")
    asm.relative("E9", "descend")

    asm.label("ascend_start")
    asm.emit("8B4104")               # otherwise ascend to the first parent
    asm.label("ascend")
    asm.emit("3BC2")
    asm.relative("0F84", "not_found")
    asm.emit("3B4808")               # keep ascending while leaving right children
    asm.relative("0F85", "use_parent")
    asm.emit("8BC8")
    asm.emit("8B4104")
    asm.relative("E9", "ascend")

    asm.label("use_parent")
    asm.emit("8BC8")
    asm.relative("E9", "inspect")

    asm.label("found_player")
    asm.emit("8BC8")                 # ecx = matching retained CPlayer
    asm.label("found")
    asm.emit("894D60")               # original local receives resolved player
    asm.relative("E9", FOUND_RVA)

    asm.label("not_found")
    asm.emit("31C9")                 # preserve stock invalid-client behavior
    asm.emit("894D60")
    asm.relative("E9", NOT_FOUND_RVA)
    return asm.finish()


if __name__ == "__main__":
    stub = build()
    print(f"length={len(stub)}")
    print(stub.hex().upper())
