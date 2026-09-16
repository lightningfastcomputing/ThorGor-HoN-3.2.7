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

    def admit(self, marker, flags, native_account_id=0x80000007, connection_id=7):
        self.vm.reg_write(reg.UC_X86_REG_EBX, self.client)
        self.vm.reg_write(reg.UC_X86_REG_EBP, self.frame)
        self.vm.reg_write(reg.UC_X86_REG_ESP, self.stack)
        self.vm.mem_write(self.frame - 0x11, bytes([marker]))
        self.vm.mem_write(self.frame - 0x48, struct.pack("<I", native_account_id))
        self.vm.mem_write(self.frame - 0x18, struct.pack("<I", connection_id))
        self.vm.mem_write(self.client + 0xCC, struct.pack("<I", flags))
        # Stock C0 admission clears this field at RVA 0x2F5A8C before our hook.
        self.vm.mem_write(self.client + 0x14, bytes(2))
        self.vm.emu_start(self.base + authority.HOOK_RVA, self.base + authority.RETURN_RVA, count=100)
        return (
            struct.unpack("<I", self.vm.mem_read(self.client + 0xCC, 4))[0],
            struct.unpack("<I", self.vm.mem_read(self.client + 0x0C, 4))[0],
            struct.unpack("<H", self.vm.mem_read(self.client + 0x14, 2))[0],
        )

    def test_actual_hook_leaves_normal_connection_field_cleared(self):
        for marker in (0, 1):
            for flags in (0, 7, 0x100, 0xFFFFFFFF):
                with self.subTest(marker=marker, flags=flags):
                    expected = flags & ~7 | (7 if marker else 0)
                    self.assertEqual(
                        self.admit(marker, flags, connection_id=0xC5F8),
                        (expected, 0x80000007, 0),
                    )

    def test_actual_hook_normalizes_marked_reconnect_and_exposes_transport_token(self):
        self.assertEqual(
            self.admit(0, 0, native_account_id=0xC0000007, connection_id=0x8001),
            (0, 0x80000007, 0x8001),
        )

    def test_generate_client_id_reuses_gateway_authenticated_native_number(self):
        host = self.client
        connection_id = self.client + 0x1000
        records = self.client + 0x2000
        return_address = self.client + 0x3000
        account_id = 0x80000007
        self.vm.mem_write(host + 0x164, struct.pack("<I", records))
        self.vm.mem_write(host + 0x168, struct.pack("<I", records + 24))
        self.vm.mem_write(
            records,
            struct.pack("<IIHBB", 0, 0, 0, 1, 0)
            + struct.pack("<IIHBB", 1, 0, 0, 1, 0),
        )
        self.vm.mem_write(connection_id, struct.pack("<H", 0x8001))
        self.vm.mem_write(
            self.stack,
            struct.pack("<III", return_address, connection_id, account_id),
        )
        self.vm.reg_write(reg.UC_X86_REG_ECX, host)
        self.vm.reg_write(reg.UC_X86_REG_ESP, self.stack)
        self.vm.emu_start(self.base + 0x2F1B80, return_address, count=100)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EAX), 1)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_ESP), self.stack + 12)

    def test_stock_generate_client_id_allocates_when_no_retained_identity_matches(self):
        host = self.client
        connection_id = self.client + 0x1000
        records = self.client + 0x2000
        stack = self.stack
        allocation_path = self.base + 0x2F1BD2
        self.vm.mem_write(host + 0x164, struct.pack("<I", records))
        self.vm.mem_write(host + 0x168, struct.pack("<I", records + 12))
        self.vm.mem_write(records, struct.pack("<IIHBB", 1, 0, 0, 1, 0))

        for account_id, candidate_connection_id in (
            (0, 0),
            (0x80000007, 7),
            (0x80000009, 3),
        ):
            with self.subTest(account_id=account_id, connection_id=candidate_connection_id):
                self.vm.mem_write(connection_id, struct.pack("<H", candidate_connection_id))
                self.vm.mem_write(
                    stack,
                    struct.pack("<III", self.client + 0x3000, connection_id, account_id),
                )
                self.vm.reg_write(reg.UC_X86_REG_ECX, host)
                self.vm.reg_write(reg.UC_X86_REG_ESP, stack)
                self.vm.emu_start(self.base + 0x2F1B80, allocation_path, count=100)
                self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EIP), allocation_path)

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

    def test_reconnect_search_uses_native_account_identity(self):
        pe = pefile.PE(data=self.game)
        base = pe.OPTIONAL_HEADER.ImageBase
        offset = pe.get_offset_from_rva(0x333A3)
        self.assertEqual(
            self.game[offset:offset + 11],
            bytes.fromhex("8B82580200003B470C757A"),
        )
        guard_offset = pe.get_offset_from_rva(0x333DD)
        self.assertEqual(
            self.game[guard_offset:guard_offset + 8],
            bytes.fromhex("8B406C3B47087416"),
        )

        self.vm.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        self.vm.mem_write(base, pe.get_memory_mapped_image())
        player = self.client + 0x1000
        self.vm.mem_write(player + 0x6C, struct.pack("<I", 1))
        self.vm.mem_write(self.client + 0x08, struct.pack("<I", 1))
        self.vm.reg_write(reg.UC_X86_REG_EAX, player)
        self.vm.reg_write(reg.UC_X86_REG_EDI, self.client)
        self.vm.emu_start(base + 0x333DD, base + 0x333FB, count=3)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EIP), base + 0x333FB)
        self.assertEqual(struct.unpack("<I", self.vm.mem_read(self.client + 0x08, 4))[0], 1)
        retained = struct.unpack("<I", self.vm.mem_read(player + 0x6C, 4))[0]
        self.assertEqual(retained, 1)

    def test_exact_hashes_idempotence_and_rejected_input(self):
        self.assertEqual(sha256(self.image), authority.OUTPUT_SHA256)
        self.assertEqual(
            sha256(self.game),
            self.catalog.get("dedicated.reconnect_client_identity").output_sha256,
        )
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
