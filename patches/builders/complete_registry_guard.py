import hashlib
import struct
import sys
from pathlib import Path


SOURCE_HASH = "45B3CE39214EFD82D12DA8B01E73494CEE983D6DB4891C7D95DF10B2EAA70B02"
FINALIZE_CALL_RVA = 0x142B45
FINALIZE_CAVE_RVA = 0x1A01CB
LOOKUP_LOAD_RVA = 0x140EFB
LOOKUP_CAVE_RVA = 0x1A0210
FALLBACK_TAIL_RVA = 0x140F21
FALLBACK_CAVE_RVA = 0x1A0240
EXPECTED_FINALIZE_CALL = bytes.fromhex("8b9014020000ffd2")
EXPECTED_LOOKUP_LOAD = bytes.fromhex("8b80bc050000")
EXPECTED_FALLBACK_TAIL = bytes.fromhex("8b40105b83c408c20400")

FINALIZE_STUB = bytes.fromhex(
    "3d00101a1972073d00a01e19720e3d00c04523722f"
    "3d00c04f2373288b901402000081fa001000197208"
    "81fa00101a19721081fa00100023720a81fa00c045237302ffd2c3"
)

# Reproduce `mov eax,[eax+0x5bc]`, then turn invalid registry objects into a
# null lookup result. The caller's existing null path creates the real entity
# from its snapshot metadata and repairs the registry entry.
LOOKUP_STUB = bytes.fromhex(
    "8b80bc050000"      # mov eax,[eax+0x5bc]
    "85c0"              # test eax,eax
    "7422"              # jz valid_return
    "8b10"              # mov edx,[eax]
    "81fa00101a19"      # cmp edx,0x191A1000
    "7208"              # jb shared_vtable
    "81fa00a01e19"      # cmp edx,0x191EA000
    "7210"              # jb valid_return
    "81fa00c04523"      # cmp edx,0x2345C000
    "7209"              # jb invalid
    "81fa00c04f23"      # cmp edx,0x234FC000
    "7301"              # jae invalid
    "c3"                # valid_return: ret
    "31c0"              # invalid: xor eax,eax
    "c3"                # ret
)

# The remote player's registry key resolves through the fallback map. Replace
# that whole return tail, validate its object, then perform the original
# function epilogue directly from the cave.
FALLBACK_STUB = bytes.fromhex(
    "8b4010"            # mov eax,[eax+0x10]
    "85c0"              # test eax,eax
    "7426"              # jz epilogue
    "8b10"              # mov edx,[eax]
    "81fa00101a19"      # cmp edx,0x191A1000
    "7208"              # jb shared_vtable
    "81fa00a01e19"      # cmp edx,0x191EA000
    "7210"              # jb valid
    "81fa00c04523"      # cmp edx,0x2345C000
    "720a"              # jb invalid
    "81fa00c04f23"      # cmp edx,0x234FC000
    "7302"              # jae invalid
    "eb02"              # valid: jmp epilogue
    "31c0"              # invalid: xor eax,eax
    "83c404"            # epilogue: discard hook return address
    "5b"                # pop ebx
    "83c408"            # add esp,8
    "c20400"            # ret 4
)


def sections(data: bytes):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    table = pe + 24 + optional_size
    for index in range(count):
        offset = table + index * 40
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, offset + 8
        )
        yield virtual_address, max(virtual_size, raw_size), raw_offset


def rva_to_file(data: bytes, rva: int) -> int:
    for virtual_address, size, raw_offset in sections(data):
        if virtual_address <= rva < virtual_address + size:
            return raw_offset + rva - virtual_address
    raise ValueError(f"RVA 0x{rva:X} is not mapped")


def call_patch(source_rva: int, target_rva: int, size: int) -> bytes:
    relative = target_rva - (source_rva + 5)
    return b"\xE8" + struct.pack("<i", relative) + b"\x90" * (size - 5)


OUTPUT_HASH = "88C4ACA3C31AF8948E1C2A33EEA2F6EE83888FA46A1DE8BE678DF32A958DF988"


def build(source: Path, target: Path) -> str:
    data = bytearray(source.read_bytes())
    digest = hashlib.sha256(data).hexdigest().upper()
    if digest != SOURCE_HASH:
        raise ValueError(f"unexpected source hash {digest}")

    finalize_call = rva_to_file(data, FINALIZE_CALL_RVA)
    finalize_cave = rva_to_file(data, FINALIZE_CAVE_RVA)
    lookup_load = rva_to_file(data, LOOKUP_LOAD_RVA)
    lookup_cave = rva_to_file(data, LOOKUP_CAVE_RVA)
    fallback_tail = rva_to_file(data, FALLBACK_TAIL_RVA)
    fallback_cave = rva_to_file(data, FALLBACK_CAVE_RVA)

    if data[finalize_call : finalize_call + 8] != EXPECTED_FINALIZE_CALL:
        raise ValueError("unexpected finalization call bytes")
    if data[lookup_load : lookup_load + 6] != EXPECTED_LOOKUP_LOAD:
        raise ValueError("unexpected registry lookup bytes")
    if data[fallback_tail : fallback_tail + 10] != EXPECTED_FALLBACK_TAIL:
        raise ValueError("unexpected fallback registry return bytes")
    if any(data[finalize_cave : fallback_cave + len(FALLBACK_STUB)]):
        raise ValueError("selected code cave is not empty")

    data[finalize_call : finalize_call + 8] = call_patch(FINALIZE_CALL_RVA, FINALIZE_CAVE_RVA, 8)
    data[finalize_cave : finalize_cave + len(FINALIZE_STUB)] = FINALIZE_STUB
    data[lookup_load : lookup_load + 6] = call_patch(LOOKUP_LOAD_RVA, LOOKUP_CAVE_RVA, 6)
    data[lookup_cave : lookup_cave + len(LOOKUP_STUB)] = LOOKUP_STUB
    data[fallback_tail : fallback_tail + 10] = call_patch(FALLBACK_TAIL_RVA, FALLBACK_CAVE_RVA, 10)
    data[fallback_cave : fallback_cave + len(FALLBACK_STUB)] = FALLBACK_STUB

    result = hashlib.sha256(data).hexdigest().upper()
    if result != OUTPUT_HASH:
        raise ValueError(f"unexpected output hash {result}")
    target.write_bytes(data)
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: build_cgame_v61_complete_registry_guard.py SOURCE_CGAME_DLL OUTPUT_CGAME_DLL", file=sys.stderr)
        return 2
    try:
        print(build(Path(argv[1]), Path(argv[2])))
    except (OSError, ValueError) as exc:
        print(f"patch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
