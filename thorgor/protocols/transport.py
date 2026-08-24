"""K2 transport framing and admission rewrites."""
from __future__ import annotations

import struct

from .packet_decoding import ConnectC0


def build_proxy_challenge(server_creation_timestamp: int, value: int) -> bytes:
    if not 0 < server_creation_timestamp <= 0xFFFFFFFF:
        raise ValueError("server creation timestamp must be a nonzero uint32")
    if not 0 < value <= 0xFFFFFFFF:
        raise ValueError("challenge value must be a nonzero uint32")
    return bytes(40) + b"\xff\xff\x40\x00" + struct.pack(
        "<IHHHI", server_creation_timestamp, 60, 0xFFFF, 0xFFFF, value
    )


def make_authorized_local_c0(data: bytes, packet: ConnectC0) -> bytes:
    if packet.flag_offset >= len(data):
        raise ValueError("external-auth flag offset is outside packet")
    rewritten = bytearray(data)
    rewritten[packet.flag_offset] &= 0xFE
    return bytes(rewritten)
