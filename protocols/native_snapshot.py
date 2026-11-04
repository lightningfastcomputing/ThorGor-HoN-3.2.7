"""Bounded decoding of HoN 3.2.7 snapshot envelopes and frame numbers.

Recovered from K2 CHostClient handlers at RVAs 30A910, 309970 and 30A670.
Entity deltas remain opaque. Only complete, validated snapshot frames count.
"""
from __future__ import annotations

import struct
import zlib


MAX_SNAPSHOT = 1024 * 1024


def unpack_snapshot(data, expected_size=None):
    if expected_size is not None:
        if expected_size > MAX_SNAPSHOT:
            raise ValueError("snapshot exceeds size limit")
        decoder = zlib.decompressobj()
        data = decoder.decompress(data, MAX_SNAPSHOT + 1)
        if not decoder.eof or decoder.unused_data or len(data) != expected_size:
            raise ValueError("invalid compressed snapshot size")
    if not 4 <= len(data) <= MAX_SNAPSHOT:
        raise ValueError("invalid snapshot length")
    return struct.unpack_from("<I", data)[0]


class SnapshotReceiver:
    def __init__(self):
        self.fragments = {}

    def receive(self, payload):
        if not payload:
            return None
        command = payload[0]
        if command in (0x5A, 0x5B):
            header = 9 if command == 0x5B else 5
            if len(payload) < header:
                raise ValueError("truncated snapshot header")
            size = struct.unpack_from("<I", payload, 1)[0]
            if size > MAX_SNAPSHOT or len(payload) != header + size:
                raise ValueError("invalid snapshot envelope length")
            expected = struct.unpack_from("<I", payload, 5)[0] if command == 0x5B else None
            return unpack_snapshot(payload[header:], expected)
        if command not in (0x5C, 0x5D, 0x5E):
            return None
        if len(payload) < 6:
            raise ValueError("truncated snapshot fragment")
        frame, index = struct.unpack_from("<IB", payload, 1)
        if frame not in self.fragments:
            if len(self.fragments) >= 8:
                self.fragments.pop(next(iter(self.fragments)))
            self.fragments[frame] = {"parts": {}, "last": None, "expected_size": None}
        state = self.fragments[frame]
        if command == 0x5C:
            part = payload[6:]
        else:
            header = 12 if command == 0x5E else 8
            if len(payload) < header:
                raise ValueError("truncated snapshot termination")
            length_offset = 10 if command == 0x5E else 6
            length = struct.unpack_from("<H", payload, length_offset)[0]
            if len(payload) != header + length:
                raise ValueError("invalid snapshot termination length")
            state["last"] = index
            state["expected_size"] = struct.unpack_from("<I", payload, 6)[0] if command == 0x5E else None
            part = payload[header:]
        previous = state["parts"].get(index)
        if previous is not None and previous != part:
            self.fragments.pop(frame)
            raise ValueError("conflicting snapshot fragment")
        state["parts"][index] = part
        if sum(map(len, state["parts"].values())) > MAX_SNAPSHOT:
            self.fragments.pop(frame)
            raise ValueError("fragmented snapshot exceeds size limit")
        last = state["last"]
        if last is None or any(number not in state["parts"] for number in range(last + 1)):
            return None
        self.fragments.pop(frame)
        complete = b"".join(state["parts"][number] for number in range(last + 1))
        decoded = unpack_snapshot(complete, state["expected_size"])
        if decoded != frame:
            raise ValueError("snapshot fragment frame mismatch")
        return decoded
