"""Protocol-47 friend presence and instant-message wire contracts."""
from __future__ import annotations

import struct
from dataclasses import dataclass

from thorgor.chat.protocol import cstr, read_cstr

CHAT_CMD_INITIAL_STATUS = 0x000B
CHAT_CMD_UPDATE_STATUS = 0x000C
CHAT_CMD_IM = 0x001C
CHAT_CMD_IM_FAILED = 0x001D
NET_CHAT_CL_GET_USER_STATUS = 0x0C05

STATUS_DISCONNECTED = 0
STATUS_CONNECTED = 3
FLAGS_PREMIUM = 1 << 6


@dataclass(frozen=True, slots=True)
class Peer:
    account_id: int
    name: str
    status: int = STATUS_CONNECTED
    flags: int = FLAGS_PREMIUM
    name_colour: str = ""
    icon: str = ""
    ascension_level: int = 0


def initial_status(peers: list[Peer]) -> bytes:
    data = bytearray(struct.pack("<I", len(peers)))
    for peer in peers:
        data += struct.pack("<IBB", peer.account_id, peer.status, peer.flags)
        data += cstr(peer.name_colour) + cstr(peer.icon)
        data += struct.pack("<I", peer.ascension_level)
    return bytes(data)


def status_update(peer: Peer) -> bytes:
    return (
        struct.pack("<IBBI", peer.account_id, peer.status, peer.flags, 0)
        + cstr("") + cstr("") + cstr(peer.name_colour) + cstr(peer.icon)
        + struct.pack("<I", peer.ascension_level)
    )


@dataclass(frozen=True, slots=True)
class InstantMessageRequest:
    target_name: str
    message: str
    send_client_information: bool

    @classmethod
    def decode(cls, payload: bytes) -> "InstantMessageRequest":
        target, offset = read_cstr(payload)
        message, offset = read_cstr(payload, offset)
        if offset >= len(payload):
            raise ValueError("instant-message payload is missing client-info flag")
        return cls(target, message, payload[offset] == 1)


def _client_info(peer: Peer) -> bytes:
    return (
        cstr(peer.name) + struct.pack("<IBB", peer.account_id, peer.status, peer.flags)
        + cstr(peer.name_colour) + cstr(peer.icon)
        + struct.pack("<I", peer.ascension_level)
    )


def first_contact(message_type: int, peer: Peer, message: str) -> bytes:
    if message_type not in (1, 2):
        raise ValueError("first-contact IM type must be 1 or 2")
    return bytes((message_type,)) + _client_info(peer) + cstr(message[:500])


def subsequent_message(sender_name: str, message: str) -> bytes:
    return b"\x00" + cstr(sender_name) + cstr(message[:500])


def failed_message(target_name: str) -> bytes:
    return cstr(target_name)
