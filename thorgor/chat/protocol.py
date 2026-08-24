"""Pure framing helpers for HoN chat protocol 47."""
from __future__ import annotations

import struct


def cstr(text: str) -> bytes:
    return text.encode("utf-8") + b"\0"


def read_cstr(data: bytes, offset: int = 0) -> tuple[str, int]:
    end = data.find(b"\0", offset)
    if end < 0:
        raise ValueError("unterminated chat string")
    return data[offset:end].decode("utf-8"), end + 1


def encode_packet(command: int, payload: bytes = b"") -> bytes:
    body = struct.pack("<H", command) + payload
    return struct.pack("<H", len(body)) + body


def extract_packet(buffer: bytes) -> tuple[tuple[int, bytes] | None, bytes]:
    if len(buffer) < 2:
        return None, buffer
    size = struct.unpack_from("<H", buffer)[0]
    if size < 2:
        raise ValueError("invalid chat packet length")
    if len(buffer) < size + 2:
        return None, buffer
    command = struct.unpack_from("<H", buffer, 2)[0]
    return (command, buffer[4:size + 2]), buffer[size + 2:]

