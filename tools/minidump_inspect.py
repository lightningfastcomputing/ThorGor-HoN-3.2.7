"""Print the exception context and selected memory from a Windows minidump."""
from __future__ import annotations

import struct
import sys
from pathlib import Path


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


data = Path(sys.argv[1]).read_bytes()
count, directory = u32(data, 8), u32(data, 12)
streams = {}
for index in range(count):
    stream_type, size, rva = struct.unpack_from("<III", data, directory + index * 12)
    streams[stream_type] = (size, rva)


def minidump_string(rva: int) -> str:
    length = u32(data, rva)
    return data[rva + 4:rva + 4 + length].decode("utf-16-le", errors="replace")


modules: list[tuple[int, int, str]] = []
if 4 in streams:
    _, rva = streams[4]
    for index in range(u32(data, rva)):
        entry = rva + 4 + index * 108
        base = u64(data, entry)
        size = u32(data, entry + 8)
        name = minidump_string(u32(data, entry + 20))
        modules.append((base, base + size, name))


def symbolic(address: int) -> str | None:
    for start, end, name in modules:
        if start <= address < end:
            return f"{Path(name).name}+0x{address - start:X}"
    return None

memory: list[tuple[int, int, int]] = []
if 5 in streams:
    _, rva = streams[5]
    for index in range(u32(data, rva)):
        entry = rva + 4 + index * 16
        start = u64(data, entry)
        size, file_rva = u32(data, entry + 8), u32(data, entry + 12)
        memory.append((start, start + size, file_rva))
if 9 in streams:
    _, rva = streams[9]
    entries, file_rva = u64(data, rva), u64(data, rva + 8)
    for index in range(entries):
        entry = rva + 16 + index * 16
        start, size = u64(data, entry), u64(data, entry + 8)
        memory.append((start, start + size, file_rva))
        file_rva += size


def virtual(address: int, size: int) -> bytes:
    for start, end, file_rva in memory:
        if start <= address and address + size <= end:
            offset = file_rva + address - start
            return data[offset:offset + size]
    return b""


_, exception_rva = streams[6]
thread_id = u32(data, exception_rva)
code = u32(data, exception_rva + 8)
address = u64(data, exception_rva + 24)
parameter_count = u32(data, exception_rva + 32)
parameters = [u64(data, exception_rva + 40 + i * 8) for i in range(parameter_count)]
context_size = u32(data, exception_rva + 160)
context_rva = u32(data, exception_rva + 164)
context = data[context_rva:context_rva + context_size]
registers = {
    "edi": u32(context, 156), "esi": u32(context, 160),
    "ebx": u32(context, 164), "edx": u32(context, 168),
    "ecx": u32(context, 172), "eax": u32(context, 176),
    "ebp": u32(context, 180), "eip": u32(context, 184),
    "esp": u32(context, 196),
}
print(f"thread={thread_id} code=0x{code:08X} address=0x{address:08X}")
print(" ".join(f"{name}=0x{value:08X}" for name, value in registers.items()))
print("parameters=" + ",".join(f"0x{value:X}" for value in parameters))
print("modules:")
for start, end, name in modules:
    print(f"  0x{start:08X}-0x{end:08X} {name}")

stack = virtual(registers["esp"], 0x1000)
print("stack module pointers:")
for offset in range(0, len(stack), 4):
    value = u32(stack, offset)
    symbol = symbolic(value)
    if symbol:
        print(f"  esp+0x{offset:03X} 0x{value:08X} {symbol}")
print("stack words around first k2 frame:")
for offset in range(0x0E0, min(len(stack), 0x180), 4):
    value = u32(stack, offset)
    print(f"  esp+0x{offset:03X} 0x{value:08X} {symbolic(value) or ''}")

for register_name in ("esi", "edi", "ebx", "ecx", "edx"):
    base = registers[register_name]
    if not base:
        continue
    print(f"{register_name} object fields at 0x{base:08X}:")
    for offset in (0x08, 0x0C, 0x14, 0x180, 0x1AC, 0x1C0, 0x8228, 0x8430):
        field = virtual(base + offset, 4)
        if len(field) == 4:
            print(f"  +0x{offset:04X}=0x{u32(field, 0):08X}")

if len(stack) >= 0x140:
    host = u32(stack, 0x134)
    link = virtual(host + 0x180, 4)
    print(f"connection list host=0x{host:08X}")
    connection = u32(link, 0) if len(link) == 4 else 0
    seen: set[int] = set()
    while connection and connection not in seen and len(seen) < 16:
        seen.add(connection)
        number = virtual(connection + 0x08, 4)
        account = virtual(connection + 0x0C, 4)
        token = virtual(connection + 0x14, 2)
        state = virtual(connection + 0x8228, 4)
        address_object = virtual(connection + 0x1AC, 0x18)
        next_link = virtual(connection + 0x8430, 4)
        print(
            f"  connection=0x{connection:08X} "
            f"number={u32(number, 0) if len(number) == 4 else None} "
            f"account=0x{u32(account, 0):08X} " if len(account) == 4 else ""
        )
        if len(token) == 2:
            print(f"    token=0x{struct.unpack_from('<H', token)[0]:04X}")
        if len(state) == 4:
            print(f"    state=0x{u32(state, 0):08X}")
        if address_object:
            print(f"    address_object={address_object.hex()}")
        connection = u32(next_link, 0) if len(next_link) == 4 else 0

addresses = list(registers.values()) + parameters
for candidate in addresses:
    if not candidate or candidate > 0xFFFFFFFF:
        continue
    blob = virtual(candidate, 0x100)
    if not blob:
        continue
    print(f"memory 0x{candidate:08X} {blob.hex()}")
    for offset in range(0, min(len(blob), 0x40), 4):
        pointer = u32(blob, offset)
        pointed = virtual(pointer, 0x100)
        if pointed:
            printable = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in pointed)
            print(f"  +0x{offset:02X} -> 0x{pointer:08X} {printable}")
