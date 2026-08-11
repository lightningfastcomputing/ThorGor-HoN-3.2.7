#!/usr/bin/env python3
"""Disassemble a virtual-address range from a 32-bit PE without modifying it."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.tools' / 'python'))

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('pe')
    parser.add_argument('virtual_address', type=lambda value: int(value, 0))
    parser.add_argument('--size', type=lambda value: int(value, 0), default=0x1000)
    parser.add_argument('--output')
    args = parser.parse_args()

    path = Path(args.pe)
    pe = pefile.PE(str(path), fast_load=True)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    rva = args.virtual_address - image_base
    if rva < 0:
        raise SystemExit(f'VA 0x{args.virtual_address:X} is below image base 0x{image_base:X}')
    offset = pe.get_offset_from_rva(rva)
    data = path.read_bytes()[offset:offset + args.size]

    disassembler = Cs(CS_ARCH_X86, CS_MODE_32)
    lines = [
        f'# file={path}',
        f'# image_base=0x{image_base:08X}',
        f'# start_va=0x{args.virtual_address:08X}',
        f'# file_offset=0x{offset:X}',
        f'# requested_size=0x{args.size:X}',
    ]
    for instruction in disassembler.disasm(data, args.virtual_address):
        raw = instruction.bytes.hex(' ')
        lines.append(
            f'{instruction.address:08X}  {raw:<24}  '
            f'{instruction.mnemonic:<8} {instruction.op_str}'.rstrip()
        )
    output = '\n'.join(lines) + '\n'
    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
    else:
        print(output, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
