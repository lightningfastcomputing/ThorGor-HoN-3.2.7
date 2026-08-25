from __future__ import annotations

import hashlib
import importlib
import struct
from pathlib import Path

from thorgor.paths import PACKAGE_ROOT
from .models import PatchManifest


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _rva_to_file(data: bytes, rva: int) -> int:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    table = pe + 24 + optional_size
    for index in range(count):
        section = table + index * 40
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", data, section + 8)
        if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
            return raw_offset + rva - virtual_address
    raise ValueError(f"RVA 0x{rva:X} is not mapped")


def _apply_operations(manifest: PatchManifest, source: Path, target: Path) -> str:
    data = bytearray(source.read_bytes())
    digest = sha256(data)
    if digest not in manifest.source_sha256:
        raise ValueError(f"unexpected {manifest.binary} source hash {digest}")
    ranges: list[tuple[int, int]] = []
    for operation in manifest.operations:
        offset = operation.offset if operation.address == "file_offset" else _rva_to_file(data, operation.offset)
        end = offset + len(operation.replacement)
        if offset < 0 or end > len(data):
            raise ValueError(f"operation at 0x{operation.offset:X} is outside the binary")
        if any(offset < prior_end and prior_start < end for prior_start, prior_end in ranges):
            raise ValueError(f"overlapping operation at 0x{operation.offset:X}")
        ranges.append((offset, end))
        if operation.expected is not None:
            actual = bytes(data[offset:offset + len(operation.expected)])
            if actual != operation.expected:
                raise ValueError(f"original bytes differ at 0x{operation.offset:X}")
        data[offset:end] = operation.replacement
    result = sha256(data)
    if result != manifest.output_sha256:
        raise ValueError(f"unexpected output hash {result}")
    target.write_bytes(data)
    return result


def _apply_builder(manifest: PatchManifest, source: Path, target: Path) -> str:
    assert manifest.builder is not None
    builder = (PACKAGE_ROOT / manifest.builder).resolve()
    if PACKAGE_ROOT.resolve() not in builder.parents or not builder.is_file():
        raise ValueError(f"invalid patch builder path: {manifest.builder}")
    module_name = "thorgor." + manifest.builder.with_suffix("").as_posix().replace("/", ".")
    module = importlib.import_module(module_name)
    result = str(module.build(source, target)).upper()
    if result != manifest.output_sha256:
        target.unlink(missing_ok=True)
        raise ValueError(f"builder returned unexpected output hash {result}")
    return result


def apply_patch(manifest: PatchManifest, source: Path, target: Path) -> str:
    source = source.resolve()
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if manifest.operations:
        return _apply_operations(manifest, source, target)
    return _apply_builder(manifest, source, target)
