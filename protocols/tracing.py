"""Passive game-transport tracing and exact hero-state packet validation."""
from __future__ import annotations

import struct

PICKER_STATE_PREFIX = bytes.fromhex("5fb703905f0100ffffffff")
PICKER_HERO_BLOCK_IDS = tuple(range(3, 9))


def describe_trace_datagram(data: bytes) -> dict[str, object]:
    record: dict[str, object] = {"bytes": len(data), "prefix": data[:32].hex()}
    if len(data) >= 7 and data[:3] == b"\x00\x00\x03":
        record.update(kind="reliable_data", sequence=struct.unpack_from("<I", data, 3)[0],
                      payload_bytes=len(data) - 7, payload_prefix=data[7:23].hex(), hex=data.hex())
    elif len(data) >= 7 and data[:3] == b"\x00\x00\x05":
        record.update(kind="reliable_ack", sequence=struct.unpack_from("<I", data, 3)[0])
    elif len(data) >= 4 and data[:3] == b"\x00\x00\x01":
        record.update(kind="control", command=data[3])
    else:
        record.update(kind="raw", hex=data.hex())
    return record


def extract_picker_hero_block_suffix(data: bytes) -> tuple[bytes, tuple[int, ...]] | None:
    if len(data) < 7 + len(PICKER_STATE_PREFIX) or data[:3] != b"\x00\x00\x03":
        return None
    payload = data[7:]
    if not payload.startswith(PICKER_STATE_PREFIX):
        return None
    cursor = len(PICKER_STATE_PREFIX)
    block_ids: list[int] = []
    while cursor < len(payload):
        if cursor + 5 > len(payload) or payload[cursor] != 0x60:
            return None
        block_id, block_size = struct.unpack_from("<HH", payload, cursor + 1)
        cursor += 5
        if block_size == 0 or block_size % 5 != 0 or cursor + block_size > len(payload):
            return None
        block_ids.append(block_id)
        cursor += block_size
    if tuple(block_ids) != PICKER_HERO_BLOCK_IDS:
        return None
    return payload[len(PICKER_STATE_PREFIX):], tuple(block_ids)


def repair_truncated_picker_packet(data: bytes, hero_suffix: bytes) -> bytes | None:
    if not hero_suffix or len(data) != 7 + len(PICKER_STATE_PREFIX):
        return None
    if data[:3] != b"\x00\x00\x03" or data[7:] != PICKER_STATE_PREFIX:
        return None
    repaired = data + hero_suffix
    extracted = extract_picker_hero_block_suffix(repaired)
    return repaired if extracted is not None and extracted[0] == hero_suffix else None
