"""Pure framing helpers for HoN chat protocol 47."""
from __future__ import annotations

import struct


def cstr(text: str) -> bytes:
    return text.encode("utf-8", errors="replace") + b"\x00"


def read_cstr(data: bytes, offset: int = 0) -> tuple[str, int]:
    end = data.find(b"\x00", offset)
    if end < 0:
        raise ValueError("unterminated string")
    return data[offset:end].decode("utf-8", errors="replace"), end + 1


def encode_packet(command: int, payload: bytes = b"") -> bytes:
    body = struct.pack("<H", command) + payload
    return struct.pack("<H", len(body)) + body


def extract_packet(buffer: bytes):
    if len(buffer) < 2:
        return None
    following = struct.unpack_from("<H", buffer, 0)[0]
    total = 2 + following
    if following < 2 or total > 1024 * 1024:
        raise ValueError(f"invalid packet length {following}")
    if len(buffer) < total:
        return None
    command = struct.unpack_from("<H", buffer, 2)[0]
    payload = buffer[4:total]
    return total, command, payload, buffer[:total]
