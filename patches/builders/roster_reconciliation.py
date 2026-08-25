"""Build ThorGor v68: reconcile only the two picking-roster state blocks.

Client evidence shows the initial state set contains blocks 1, 2, 13, and 14.
Blocks 13 and 14 are the two team picking rosters.  v68 retains v67's guarded
per-client comparison only for those two block indexes, preventing the new path
from touching gameplay/entity-definition blocks 1 and 2 during handoff.
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path


SOURCE_SHA256 = "6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF"
V67_SHA256 = "79B6DF5DD59853C8941800C5BAEA9D21FA53FBC2753646E5686551B468FE7E61"
OUTPUT_SHA256 = "142FCDB10AA866D28100090B3C68597D3C35651230FB40EEFD3C51242F3E1E89"

RECONCILE_CLIENT_HEAD = 0x70D6C1
RECONCILE_LOOP = 0x70D6C7
RECONCILE_DONE = 0x70D720
ROSTER_GUARD = 0x70D740


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def rel32(instruction_rva: int, target_rva: int) -> bytes:
    return struct.pack("<i", target_rva - (instruction_rva + 5))


def jump(instruction_rva: int, target_rva: int) -> bytes:
    return b"\xE9" + rel32(instruction_rva, target_rva)


def jcc(instruction_rva: int, target_rva: int, condition: int) -> bytes:
    return bytes((0x0F, condition)) + struct.pack(
        "<i", target_rva - (instruction_rva + 6)
    )


def load_v67_builder():
    from . import safe_reconciliation

    return safe_reconciliation


def build(source: Path, target: Path) -> str:
    if sha256(source.read_bytes()) != SOURCE_SHA256:
        raise ValueError("unexpected v57 source hash")

    v67 = load_v67_builder()
    v67.build(source, target)
    data = bytearray(target.read_bytes())
    if sha256(data) != V67_SHA256:
        raise ValueError("intermediate v67 hash mismatch")

    original = bytes.fromhex("8bbf80010000")
    actual = bytes(data[RECONCILE_CLIENT_HEAD : RECONCILE_CLIENT_HEAD + 6])
    if actual != original:
        raise ValueError(
            f"v67 client-head instruction mismatch: expected {original.hex()}, "
            f"got {actual.hex()}"
        )
    if any(data[ROSTER_GUARD : ROSTER_GUARD + 0x40]):
        raise ValueError("v68 roster guard cave is not empty")

    # The wrapper has already executed PUSHAD.  Reject every block except the
    # Legion and Hellbourne picking rosters, then resume the original v67 loop.
    guard = bytearray.fromhex("83fb0d")  # cmp ebx,13
    guard += jcc(ROSTER_GUARD + len(guard), RECONCILE_DONE, 0x82)  # jb done
    guard += bytes.fromhex("83fb0e")  # cmp ebx,14
    guard += jcc(ROSTER_GUARD + len(guard), RECONCILE_DONE, 0x87)  # ja done
    guard += original  # mov edi,[edi+0x180]
    guard += jump(ROSTER_GUARD + len(guard), RECONCILE_LOOP)

    data[RECONCILE_CLIENT_HEAD : RECONCILE_CLIENT_HEAD + 6] = (
        jump(RECONCILE_CLIENT_HEAD, ROSTER_GUARD) + b"\x90"
    )
    data[ROSTER_GUARD : ROSTER_GUARD + len(guard)] = guard

    result = sha256(data)
    if OUTPUT_SHA256 and result != OUTPUT_SHA256:
        raise ValueError(f"unexpected v68 output hash {result}")
    target.write_bytes(data)
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: build_k2_v68.py K2_V57_DLL OUTPUT_K2_DLL", file=sys.stderr)
        return 2
    try:
        print(build(Path(argv[1]), Path(argv[2])))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"patch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
