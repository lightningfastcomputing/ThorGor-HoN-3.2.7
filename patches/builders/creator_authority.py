"""Creator-only native authority on the exact v77 K2 milestone.

All addresses are RVAs. K2 3.2.7.1's text mapping also uses identical file
offsets here; conversion is still explicit. The paired authenticated proxy
owns C0 marker bit zero. The remaining request bits never grant authority.
"""
from __future__ import annotations

import struct
from pathlib import Path

from thorgor.patches.engine import _rva_to_file, sha256

SOURCE_SHA256 = "25B1BB066FE3166BF83A4AA52D6FBB0B9FB972F43161F3D73DFA930090CE7026"
OUTPUT_SHA256 = "A4F9856A53A01D212CAE03EA1746F6594904F8D255956AD6D849ABD467281A77"
MARKER_REJECTION_RVA = 0x2F5982
HOOK_RVA = 0x2F5AD6
RETURN_RVA = 0x2F5ADD
CAVE_RVA = 0x70D740
PROMOTION_RVA = 0x2F8E1E
ACCOUNT_RESET_RVA = 0x2F8E50
CAPTURE_RVA = 0x2F555C
CAPTURE_CAVE_RVA = 0x70D780
ALLOCATOR_CALL_RVA = 0x2F8E63
ALLOCATOR_CAVE_RVA = 0x70D7C0
CONNECTION_LOOKUP_RVA = 0x70D4EA
CONNECTION_LOOKUP_RESUME_RVA = 0x70D4EF
CONNECTION_LOOKUP_NEXT_RVA = 0x70D517
CONNECTION_LOOKUP_CAVE_RVA = 0x70D900


def jump(source: int, target: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target - source - 5)


def authority_stub() -> bytes:
    code = bytes.fromhex(
        "5051"            # EDX is the live CPacket pointer; preserve EAX/ECX too
        "8b8538fdffff"    # authenticated account saved before map::insert
        "a900000040"      # trusted gateway supplied a reconnect token
        "740a"            # never accept an unmarked client token
        "8b8d34fdffff"    # token saved before [ebp-0x18] is reused
        "66894b14"
        "25ffffffbf"      # remove private reconnect marker from the account
        "89430c"          # retain normalized account identity
        "5958"
        "83a3cc000000f8"  # clear the composite local/admin/host bits
        "f645ef01"        # test byte [ebp-0x11],1: approved creator only
        "7407"            # skip granting creator bits for ordinary joiners
        "838bcc00000007"  # retain the creator's original flags
    )
    return code + jump(CAVE_RVA + len(code), RETURN_RVA)

def capture_stub() -> bytes:
    # Private DWORD locals below the original frame, above the saved registers.
    code = bytes.fromhex(
        "898538fdffff"    # saved account = EAX
        "ff75e8"          # push original token
        "8f8534fdffff"    # pop saved token
        "8bf8528bce"      # displaced mov edi,eax; push edx; mov ecx,esi
    )
    return code + jump(CAPTURE_CAVE_RVA + len(code), CAPTURE_RVA + 5)


def allocator_stub() -> bytes:
    """Reclaim a local allocation only after checking every linked transport.

    Record byte +0x0a means token==0 (local allocation), NOT live. ThorGor
    keeps disconnected CClientConnections linked after C3. Retire their number
    before native lookup/send helpers resolve the new one. Never change the
    retained allocation, CPlayer, player map, team or hero.
    """
    code = bytearray()
    labels: dict[str, int] = {}
    branches: list[tuple[int, str]] = []

    def emit(hex_bytes: str) -> None:
        code.extend(bytes.fromhex(hex_bytes))

    def label(name: str) -> None:
        labels[name] = len(code)

    def branch(opcode: str, target: str) -> None:
        emit(opcode)
        branches.append((len(code), target))
        code.extend(bytes(4))

    emit("535657")                 # preserve EBX/ESI/EDI
    emit("8b5c2410 0fb713")         # EBX=&token; EDX=token
    emit("81fa00800000")           # private tokens are 0x8000..0x807f
    branch("0f82", "stock")
    emit("81fa7f800000")
    branch("0f87", "stock")
    emit("8b7c2414 89f8 25000000c0 3d00000080")
    branch("0f85", "stock")       # only normalized local accounts
    emit("81e27f000000")           # full native number, not low-byte compare
    emit("8b8164010000")
    label("record")
    emit("3b8168010000")
    branch("0f84", "fallback")
    emit("3910")
    branch("0f84", "account")
    emit("83c00c")
    branch("e9", "record")
    label("account")
    emit("397804")
    branch("0f85", "fallback")
    emit("8bb180010000")
    label("check")
    emit("85f6")
    branch("0f84", "retire_begin")
    emit("395608")
    branch("0f85", "next")
    emit("397e0c")
    branch("0f85", "fallback")
    emit("83be2882000000")          # CClientConnection state must be 0
    branch("0f85", "fallback")
    label("next")
    emit("8bb630840000")
    branch("e9", "check")
    label("retire_begin")
    emit("8bb180010000")
    label("retire")
    emit("85f6")
    branch("0f84", "reclaimed")
    emit("395608")
    branch("0f85", "retire_next")
    emit("c74608ffffffff")         # invalidate only the retired transport
    label("retire_next")
    emit("8bb630840000")
    branch("e9", "retire")
    label("reclaimed")
    emit("89d0 5f5e5b c20800")     # original number, thiscall ret 8
    label("fallback")
    emit("66c7030000")             # no private token reaches stock lookup
    label("stock")
    emit("5f5e5b")
    code.extend(jump(ALLOCATOR_CAVE_RVA + len(code), 0x2F1B80))
    for offset, target in branches:
        struct.pack_into("<i", code, offset, labels[target] - offset - 4)
    return bytes(code)


def connection_lookup_guard_stub() -> bytes:
    """Avoid comparing destroyed address strings on irrelevant transports.

    The linked-transport lookup runs before C0 admission and requires both the
    connection token and source address to match. K2 normally compares the
    address first. During reconnect, older connections can remain linked after
    their address string is no longer valid, including the live match host.
    Compare the always-live uint16 token first, then state, and touch the string
    only for a matching live transport. This preserves the original predicate.
    """
    code = bytearray(bytes.fromhex("66395e14"))        # cmp [esi+0x14],bx
    code.extend(bytes.fromhex("0f85"))                 # token mismatch -> next
    code.extend(struct.pack("<i", CONNECTION_LOOKUP_NEXT_RVA - (CONNECTION_LOOKUP_CAVE_RVA + len(code) + 4)))
    code.extend(bytes.fromhex("83be2882000000"))      # cmp [esi+0x8228],0
    code.extend(bytes.fromhex("0f84"))                 # disconnected -> next
    code.extend(struct.pack("<i", CONNECTION_LOOKUP_NEXT_RVA - (CONNECTION_LOOKUP_CAVE_RVA + len(code) + 4)))
    code.extend(bytes.fromhex("89f88b5014"))          # displaced instructions
    code.extend(jump(CONNECTION_LOOKUP_CAVE_RVA + len(code), CONNECTION_LOOKUP_RESUME_RVA))
    return bytes(code)


def operations() -> tuple[tuple[int, bytes, bytes], ...]:
    code = authority_stub()
    return (
        # Enter the proven local constructor even for a creator-marked C0.
        (MARKER_REJECTION_RVA, bytes.fromhex("0f859a020000"), b"\x90" * 6),
        (HOOK_RVA, bytes.fromhex("838bcc00000007"), jump(HOOK_RVA, CAVE_RVA) + b"\x90\x90"),
        (CAVE_RVA, bytes(0x40), code.ljust(0x40, b"\0")),
        # Eight private bytes; all original EBP-relative locals stay in place.
        (0x2F53F8, bytes.fromhex("81ecb8020000"), bytes.fromhex("81ecc0020000")),
        (CAPTURE_RVA, bytes.fromhex("8bf8528bce"), jump(CAPTURE_RVA, CAPTURE_CAVE_RVA)),
        (CAPTURE_CAVE_RVA, bytes(0x40), capture_stub().ljust(0x40, b"\0")),
        # AuthSuccess's legacy account/roster fallback must not override the
        # master decision. Host-flag testing and NETCMD_GAME_HOST stay native.
        (PROMOTION_RVA, bytes.fromhex("838dcc00000001"), b"\x90" * 7),
        # The local admission branch used to overwrite the parsed identity
        # immediately before GenerateClientID/CPlayer initialization.
        (ACCOUNT_RESET_RVA, bytes.fromhex("897d0c"), b"\x90" * 3),
        # Intercept only local AuthSuccess; retain GenerateClientID verbatim.
        (ALLOCATOR_CALL_RVA, bytes.fromhex("e8188dffff"),
         b"\xe8" + struct.pack("<i", ALLOCATOR_CAVE_RVA - ALLOCATOR_CALL_RVA - 5)),
        (ALLOCATOR_CAVE_RVA, bytes(0x140), allocator_stub().ljust(0x140, b"\0")),
        # ReadPackets performs this lookup before C0 admission. Old transports
        # remain linked after their address strings become unsafe. Short-circuit
        # the token/state predicates before basic_string::compare.
        (CONNECTION_LOOKUP_RVA, bytes.fromhex("89f88b5014"),
         jump(CONNECTION_LOOKUP_RVA, CONNECTION_LOOKUP_CAVE_RVA)),
        (CONNECTION_LOOKUP_CAVE_RVA, bytes(0x40),
         connection_lookup_guard_stub().ljust(0x40, b"\0")),
    )


def build(source: Path, target: Path) -> str:
    data = bytearray(source.read_bytes())
    if sha256(data) != SOURCE_SHA256:
        raise ValueError("creator authority requires the verified v77 K2 milestone")
    for rva, expected, replacement in operations():
        offset = _rva_to_file(data, rva)
        if data[offset:offset + len(expected)] != expected:
            raise ValueError(f"unexpected authority patch bytes at RVA 0x{rva:X}")
        data[offset:offset + len(replacement)] = replacement
    digest = sha256(data)
    if digest != OUTPUT_SHA256:
        raise ValueError(f"unexpected creator-authority output hash {digest}")
    target.write_bytes(data)
    return digest
