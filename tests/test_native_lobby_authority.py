"""Execute patched retail instructions; optional local binary fixtures only."""
import os
import struct
import tempfile
import unittest
from pathlib import Path

from thorgor.patches.builders import creator_authority as authority
from thorgor.patches.catalog import PatchCatalog
from thorgor.patches.engine import apply_patch, sha256
from thorgor.patches.installer import install_game_capacity, install_k2

try:
    import pefile
    import unicorn as uc
    from unicorn import x86_const as reg
except ImportError:
    uc = None

HON_HOME = os.environ.get("THORGOR_TEST_HON_HOME")


@unittest.skipUnless(uc is not None and HON_HOME, "requires unicorn, pefile and THORGOR_TEST_HON_HOME")
class NativeLobbyAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="thorgor-native-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        cls.home = Path(HON_HOME)
        cls.catalog = PatchCatalog()
        (cls.work / "game").mkdir()
        (cls.work / "k2.dll").write_bytes((cls.home / "k2.dll.thorgor_stock_3.2.7.1").read_bytes())
        (cls.work / "game" / "game.dll").write_bytes(
            (cls.home / "game/game.dll.thorgor_stock_3.2.7.1").read_bytes()
        )
        install_k2(cls.work)
        install_game_capacity(cls.work)
        cls.image = (cls.work / "k2.dll").read_bytes()
        cls.game = (cls.work / "game/game.dll").read_bytes()

    def setUp(self):
        self.vm = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
        pe = pefile.PE(data=self.image)
        self.base = pe.OPTIONAL_HEADER.ImageBase
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095
        self.vm.mem_map(self.base, size)
        self.vm.mem_write(self.base, pe.get_memory_mapped_image())
        self.vm.mem_map(0x100000, 0x20000)
        self.client, self.frame, self.stack = 0x108000, 0x118000, 0x117000

    def admit(self, marker, flags):
        self.vm.reg_write(reg.UC_X86_REG_EBX, self.client)
        self.vm.reg_write(reg.UC_X86_REG_EBP, self.frame)
        self.vm.reg_write(reg.UC_X86_REG_ESP, self.stack)
        self.vm.mem_write(self.frame - 0x11, bytes([marker]))
        self.vm.mem_write(self.client + 0xCC, struct.pack("<I", flags))
        self.vm.emu_start(self.base + authority.HOOK_RVA, self.base + authority.RETURN_RVA, count=100)
        return struct.unpack("<I", self.vm.mem_read(self.client + 0xCC, 4))[0]

    def test_actual_hook_grants_only_marker_bit_zero_and_preserves_other_flags(self):
        for marker in (0, 1, 2, 3, 0xFE, 0xFF):
            for flags in (0, 7, 0x100, 0xFFFFFFFF):
                with self.subTest(marker=marker, flags=flags):
                    expected = flags & ~7 | (7 if marker & 1 else 0)
                    self.assertEqual(self.admit(marker, flags), expected)
                    self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_ESP), self.stack)
                    self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EBX), self.client)

    def test_auth_success_cannot_repromote_joiner_and_only_creator_gets_host_event(self):
        for creator in (False, True):
            self.admit(int(creator), 0)
            self.vm.reg_write(reg.UC_X86_REG_EBP, self.client)
            self.vm.reg_write(reg.UC_X86_REG_ESP, self.stack)
            events = []
            writer = self.base + 0x32220
            self.vm.mem_write(writer, b"\xc2\x04\x00")

            def capture(vm, address, size, data):
                if address == writer:
                    esp = vm.reg_read(reg.UC_X86_REG_ESP)
                    events.append(struct.unpack("<I", vm.mem_read(esp + 4, 4))[0])

            hook = self.vm.hook_add(uc.UC_HOOK_CODE, capture)
            self.vm.emu_start(self.base + authority.PROMOTION_RVA, self.base + 0x2F8E46, count=100)
            self.vm.hook_del(hook)
            self.assertEqual(events, [0x69, 1] if creator else [])
            self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_ESP), self.stack)

    def test_actual_capacity_guard_accepts_second_player_and_rejects_eleventh(self):
        pe = pefile.PE(data=self.game)
        base = pe.OPTIONAL_HEADER.ImageBase
        self.vm.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        self.vm.mem_write(base, pe.get_memory_mapped_image())
        self.vm.reg_write(reg.UC_X86_REG_EDI, self.client)
        self.vm.reg_write(reg.UC_X86_REG_EBX, 0)
        self.vm.mem_write(self.client + 0xCC, bytes(4))
        self.vm.mem_write(self.client + 0xDD, b"\0")
        for count in (0, 1, 9, 10, 11):
            self.vm.reg_write(reg.UC_X86_REG_EAX, count)
            self.vm.emu_start(base + 0x337EC, base + 0x33825, count=2)
            accepted = self.vm.reg_read(reg.UC_X86_REG_EIP) == base + 0x33825
            self.assertEqual(accepted, count < 10)

    def test_exact_hashes_idempotence_and_rejected_input(self):
        self.assertEqual(sha256(self.image), authority.OUTPUT_SHA256)
        self.assertEqual(sha256(self.game), self.catalog.get("dedicated.server_capacity").output_sha256)
        self.assertIn("already installed", install_k2(self.work))
        self.assertIn("already installed", install_game_capacity(self.work))
        bad, target = self.work / "bad.dll", self.work / "must-not-exist.dll"
        bad.write_bytes(b"unknown binary")
        with self.assertRaises(ValueError):
            apply_patch(self.catalog.get("dedicated.creator_authority"), bad, target)
        self.assertFalse(target.exists())

    def test_v77_upgrade_preserves_previous_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            baseline = (self.work / "k2.dll.thorgor_v77_baseline").read_bytes()
            (home / "k2.dll").write_bytes(baseline)
            install_k2(home)
            self.assertEqual((home / "k2.dll").read_bytes(), self.image)
            backup = home / f"k2.dll.thorgor_before_{authority.SOURCE_SHA256.lower()}"
            self.assertEqual(backup.read_bytes(), baseline)
