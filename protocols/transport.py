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


def make_authorized_local_c0(data: bytes, packet: ConnectC0, *, is_match_host: bool) -> bytes:
    """Encode the master decision for the paired K2 creator-authority patch.

    The legacy parser calls this external_auth; native K2 consumes this byte
    as the C0 host-request marker. Other bits are preserved, never trusted as
    creator authority. Do not use this rewrite with an unpatched v77 K2.
    """
    if not 0 <= packet.flag_offset < len(data):
        raise ValueError("external-auth flag offset is outside packet")
    rewritten = bytearray(data)
    rewritten[packet.flag_offset] = (rewritten[packet.flag_offset] & 0xFE) | int(is_match_host)
    return bytes(rewritten)
