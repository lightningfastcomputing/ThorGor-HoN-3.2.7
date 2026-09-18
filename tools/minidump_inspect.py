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
