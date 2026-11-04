"""Execute the successor cleanup against a rebuilt frozen v39 image."""
import os
from pathlib import Path
import struct
import tempfile
import unittest

from thorgor.patches.builders import managed_registry as repair
from thorgor.patches.installer import install_k2
from thorgor.patches.engine import sha256

try:
    import pefile
    import unicorn as uc
    from unicorn import x86_const as reg
except ImportError:
    uc = None


@unittest.skipUnless(uc is not None and os.environ.get("THORGOR_TEST_HON_HOME"),
                     "requires native emulation fixtures")
class ManagedRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="thorgor-registry-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        source = Path(os.environ["THORGOR_TEST_HON_HOME"]) / "k2.dll.thorgor_stock_3.2.7.1"
        frozen = directory / "k2.dll"
        frozen.write_bytes(source.read_bytes())
        install_k2(directory)
        target = directory / "candidate.dll"
        cls.digest = repair.build(frozen, target)
        cls.image = target.read_bytes()
        cls.frozen_hash = sha256(frozen.read_bytes())

    def setUp(self):
        pe = pefile.PE(data=self.image)
        self.base = pe.OPTIONAL_HEADER.ImageBase
        self.vm = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
        self.vm.mem_map(self.base, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        self.vm.mem_write(self.base, pe.get_memory_mapped_image())
        self.vm.mem_map(0x100000, 0x50000)
        self.server, self.creator, self.joiner, self.third = 0x100000, 0x110000, 0x120000, 0x130000
        self.stack = 0x149000
        self.write(self.server + 0x180, self.creator)
        self.write(self.creator + 0x8430, self.joiner)
        self.write(self.joiner + 0x8430, self.third)
        self.write(self.third + 0x8430, 0)
        self.vm.reg_write(reg.UC_X86_REG_EDI, self.server)
        self.vm.reg_write(reg.UC_X86_REG_ESP, self.stack)
        self.freed = []
        self.vm.mem_write(self.base + repair.FREE_RVA, b"\xc3")

        def free(vm, address, size, data):
            if address == self.base + repair.FREE_RVA:
                pointer = vm.reg_read(reg.UC_X86_REG_ESI)
                self.freed.append((pointer, self.read(pointer + 0x8430)))
                self.write(pointer + 0x8430, 0xDEADBEEF)
        self.vm.hook_add(uc.UC_HOOK_CODE, free)

    def write(self, address, value):
        self.vm.mem_write(address, struct.pack("<I", value))

    def read(self, address):
        return struct.unpack("<I", self.vm.mem_read(address, 4))[0]

    def run_cleanup(self, managed=True):
        self.vm.mem_write(self.server + 0x2D0, bytes([managed]))
        end = repair.RETURN_RVA if managed else repair.HOOK_RVA + 6
        self.vm.emu_start(self.base + repair.HOOK_RVA, self.base + end, count=80)

    def test_managed_head_is_detached_and_successor_chain_survives_free(self):
        self.run_cleanup()
        self.assertEqual(self.freed, [(self.creator, 0)])
        self.assertEqual(self.read(self.server + 0x180), self.joiner)
        self.assertEqual(self.read(self.joiner + 0x8430), self.third)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_ESP), self.stack)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EDI), self.server)

    def test_last_managed_head_and_already_empty_registry(self):
        self.write(self.creator + 0x8430, 0)
        self.run_cleanup()
        self.assertEqual(self.read(self.server + 0x180), 0)
        self.assertEqual(len(self.freed), 1)
        self.run_cleanup()
        self.assertEqual(len(self.freed), 1)

    def test_unmanaged_path_keeps_original_cleanup(self):
        self.run_cleanup(managed=False)
        self.assertEqual(self.freed, [])
        self.assertEqual(self.read(self.server + 0x180), self.creator)
        self.assertEqual(self.read(self.creator + 0x8430), self.joiner)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_ESI), self.creator)

    def test_actual_snapshot_dispatch_loop_visits_survivors_after_head_removal(self):
        self.run_cleanup()
        for pointer in (self.joiner, self.third):
            self.write(pointer + 0x8228, 4)
        recipients = []
        writer = self.base + 0x2FB590
        self.vm.mem_write(writer, b"\xc2\x04\x00")
        def capture(vm, address, size, data):
            if address == writer:
                recipients.append(vm.reg_read(reg.UC_X86_REG_ECX))
        self.vm.hook_add(uc.UC_HOOK_CODE, capture)
        stop = 0x148000
        self.vm.mem_write(self.stack, struct.pack("<II", stop, self.server))
        self.vm.reg_write(reg.UC_X86_REG_ESP, self.stack)
        self.vm.emu_start(self.base + 0x70D5A0, stop, count=100)
        self.assertEqual(recipients, [self.joiner, self.third])
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_ESP), self.stack + 8)

    def test_exact_output_and_frozen_input_preserved(self):
        self.assertEqual(self.digest, repair.OUTPUT_SHA256)
        self.assertEqual(self.frozen_hash, repair.SOURCE_SHA256)
