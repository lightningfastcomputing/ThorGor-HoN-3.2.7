"""K2 transport framing and admission rewrites."""
from __future__ import annotations

import struct

from .packet_decoding import ConnectC0

RECONNECT_ACCOUNT_MARKER = 0x40000000


def build_proxy_challenge(server_creation_timestamp: int, value: int) -> bytes:
    if not 0 < server_creation_timestamp <= 0xFFFFFFFF:
        raise ValueError("server creation timestamp must be a nonzero uint32")
    if not 0 < value <= 0xFFFFFFFF:
        raise ValueError("challenge value must be a nonzero uint32")
    return bytes(40) + b"\xff\xff\x40\x00" + struct.pack(
        "<IHHHI", server_creation_timestamp, 60, 0xFFFF, 0xFFFF, value
    )


def make_authorized_local_c0(
    data: bytes,
    packet: ConnectC0,
    *,
    is_match_host: bool,
    is_reconnect: bool = False,
    account_id: int,
    connection_id: int | None = None,
) -> bytes:
    """Encode the master decision for the paired K2 creator-authority patch.

    The legacy parser calls this external_auth; native K2 consumes this byte
    as the C0 host-request marker. Other bits are preserved, never trusted as
    creator authority. Do not use this rewrite with an unpatched v77 K2.
    """
    if not 0 <= packet.flag_offset < len(data):
        raise ValueError("external-auth flag offset is outside packet")
    if not 0 < account_id < RECONNECT_ACCOUNT_MARKER:
        raise ValueError("account ID must fit the local native identity namespace")
    if not 0 <= packet.account_id_offset <= len(data) - 4:
        raise ValueError("account ID offset is outside packet")
    if connection_id is not None and not 0 < connection_id <= 0xFFFF:
        raise ValueError("connection ID must be a nonzero uint16")
    rewritten = bytearray(data)
    # K2/game.dll need a stable, unique account identity to associate a new
    # transport with a disconnected CPlayer.  Keep it negative when interpreted
    # as int32 so retail profile/avatar lookup still treats this as a local user.
    # The private marker authenticates the gateway-assigned connection token.
    # K2 removes it before game.dll sees the account.  It is required on the
    # first admission as well as reconnect so stock GenerateClientID stores the
    # same persistent token in its allocation record on both sides of a drop.
    native_account_id = 0x80000000 | account_id | RECONNECT_ACCOUNT_MARKER
    struct.pack_into("<I", rewritten, packet.account_id_offset, native_account_id)
    if connection_id is not None:
        connection_id_offset = (
            4
            + len(packet.product.encode("utf-8")) + 1
            + len(packet.version.encode("utf-8")) + 1
            + 4
        )
        if connection_id_offset + 2 > len(rewritten):
            raise ValueError("connection ID offset is outside packet")
        struct.pack_into("<H", rewritten, connection_id_offset, connection_id)
    # K2 masks this byte to bit zero, so it carries creator authority only.
    # Reconnect admission is carried in the authenticated account namespace;
    # the paired K2 hook removes that marker before the game sees the account.
    rewritten[packet.flag_offset] = (
        (rewritten[packet.flag_offset] & 0xFC) | int(is_match_host)
    )
    return bytes(rewritten)
