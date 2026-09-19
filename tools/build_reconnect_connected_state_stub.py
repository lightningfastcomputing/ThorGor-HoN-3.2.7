"""Build the reconnect v31 native connected-state transition.

The retained CPlayer already has the correct account, hero and fresh client
number when this stub runs.  Mirror CPlayer::Connected exactly: clear the
disconnected bit, set the connected-transition bit and cancel the disconnect
deadline.  No lobby, team-roster or map membership is changed here.
"""
from __future__ import annotations

import struct


BASE_RVA = 0x73C00
IDENTITY_CAVE_RVA = 0x15691


def build() -> bytes:
    code = bytearray()
    code.extend(bytes.fromhex("6681A05A030000FEFF"))  # flags &= ~1
    code.extend(bytes.fromhex("6683885A03000040"))    # flags |= 0x40
    code.extend(bytes.fromhex("C780A4030000FFFFFFFF"))  # deadline = UINT32_MAX
    next_rva = BASE_RVA + len(code) + 5
    code.append(0xE9)
    code.extend(struct.pack("<i", IDENTITY_CAVE_RVA - next_rva))
    return bytes(code)


if __name__ == "__main__":
    stub = build()
    print(f"length={len(stub)}")
    print(stub.hex().upper())
