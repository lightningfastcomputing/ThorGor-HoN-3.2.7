"""Build ThorGor v67: guarded per-client state reconciliation.

v67 retains v66's per-client revision comparison, but changes the periodic
delivery call back to K2's original QueueStateBlock entry point.  That restores
the connection-state and assigned-client-number guards that v66 bypassed and
which are required while a client transitions from picking into gameplay.
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path


SOURCE_SHA256 = "6F5FC1F7BF4E01CDEB0360A6F703299F5422F2C06A104FADCB24FD96A546B8DF"
V66_SHA256 = "2BC131F1C40D9F84CAD288426B14B0DB1EE58E43FC64DB86FF5AEFFC82D58657"
OUTPUT_SHA256 = "79B6DF5DD59853C8941800C5BAEA9D21FA53FBC2753646E5686551B468FE7E61"

RECONCILE_QUEUE_CALL = 0x70D710
UNSAFE_QUEUE_WRAPPER = 0x70D680
ORIGINAL_QUEUE_BLOCK = 0x2F75D0


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def call(instruction_rva: int, target_rva: int) -> bytes:
    return b"\xE8" + struct.pack("<i", target_rva - (instruction_rva + 5))


def load_v66_builder():
    from . import state_revision_reconciliation

    return state_revision_reconciliation


def build(source: Path, target: Path) -> str:
    if sha256(source.read_bytes()) != SOURCE_SHA256:
        raise ValueError("unexpected v57 source hash")

    v66 = load_v66_builder()
    v66.build(source, target)
    data = bytearray(target.read_bytes())
    if sha256(data) != V66_SHA256:
        raise ValueError("intermediate v66 hash mismatch")

    unsafe = call(RECONCILE_QUEUE_CALL, UNSAFE_QUEUE_WRAPPER)
    actual = bytes(data[RECONCILE_QUEUE_CALL : RECONCILE_QUEUE_CALL + 5])
    if actual != unsafe:
        raise ValueError(
            f"v66 reconciliation call mismatch: expected {unsafe.hex()}, "
            f"got {actual.hex()}"
        )

    data[RECONCILE_QUEUE_CALL : RECONCILE_QUEUE_CALL + 5] = call(
        RECONCILE_QUEUE_CALL, ORIGINAL_QUEUE_BLOCK
    )
    result = sha256(data)
    if OUTPUT_SHA256 and result != OUTPUT_SHA256:
        raise ValueError(f"unexpected v67 output hash {result}")
    target.write_bytes(data)
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: build_k2_v67.py K2_V57_DLL OUTPUT_K2_DLL", file=sys.stderr)
        return 2
    try:
        print(build(Path(argv[1]), Path(argv[2])))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"patch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
