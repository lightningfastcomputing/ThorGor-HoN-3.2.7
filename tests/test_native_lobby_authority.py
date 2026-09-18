"""Execute patched retail instructions; optional local binary fixtures only."""
import os
import struct
import tempfile
import unittest
from pathlib import Path

from thorgor.patches.builders import creator_authority as authority
from thorgor.patches.builders import reconnect_client_identity as reconnect
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
        self.vm.mem_map(0x100000, 0x80000)
        self.client, self.frame, self.stack = 0x108000, 0x118000, 0x117000

    def admit(self, marker, flags, native_account_id=0x80000007, connection_id=7):
        # Execute the early capture with real parser register values, then
        # reproduce the subsequent map-insert and constructor local lifetimes.
        self.vm.reg_write(reg.UC_X86_REG_EBP, self.frame)
        self.vm.reg_write(reg.UC_X86_REG_ESP, self.stack)
        self.vm.reg_write(reg.UC_X86_REG_EAX, native_account_id)
        self.vm.mem_write(self.frame - 0x18, struct.pack("<I", connection_id))
        self.vm.emu_start(self.base + authority.CAPTURE_RVA,
                          self.base + authority.CAPTURE_RVA + 5, count=100)
        self.vm.reg_write(reg.UC_X86_REG_EBX, self.client)
        self.vm.reg_write(reg.UC_X86_REG_EBP, self.frame)
        self.vm.reg_write(reg.UC_X86_REG_ESP, self.stack)
        self.vm.mem_write(self.frame - 0x11, bytes([marker]))
        self.vm.mem_write(self.frame - 0x48, struct.pack("<I", 1))
        self.vm.mem_write(self.frame - 0x18, struct.pack("<I", self.client))
        self.vm.mem_write(self.client + 0xCC, struct.pack("<I", flags))
        # Stock C0 admission clears this field at RVA 0x2F5A8C before our hook.
        self.vm.mem_write(self.client + 0x14, bytes(2))
        self.vm.emu_start(self.base + authority.HOOK_RVA, self.base + authority.RETURN_RVA, count=100)
        return (
            struct.unpack("<I", self.vm.mem_read(self.client + 0xCC, 4))[0],
            struct.unpack("<I", self.vm.mem_read(self.client + 0x0C, 4))[0],
            struct.unpack("<H", self.vm.mem_read(self.client + 0x14, 2))[0],
        )

    def test_actual_hook_accepts_only_gateway_marked_reconnect_token(self):
        for marker in (0, 1):
            for flags in (0, 7, 0x100, 0xFFFFFFFF):
                with self.subTest(marker=marker, flags=flags):
                    expected = flags & ~7 | (7 if marker else 0)
                    self.assertEqual(
                        self.admit(marker, flags, native_account_id=0xC0000007, connection_id=0xC5F8),
                        (expected, 0x80000007, 0xC5F8),
                    )

    def test_actual_hook_rejects_unmarked_client_connection_token(self):
        self.assertEqual(
            self.admit(0, 0, native_account_id=0x80000007, connection_id=0x8001),
            (0, 0x80000007, 0),
        )

    def test_reconnect_hook_preserves_packet_pointer_and_registers(self):
        packet = 0x150000
        self.vm.reg_write(reg.UC_X86_REG_EDX, packet)
        self.admit(0, 0, native_account_id=0xC0000003, connection_id=0x8001)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EDX), packet)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_ESP), self.stack)
        # Continue through the real push/call: v19 passed CClientConnection as
        # CPacket, whose +8 is -1, and ReadInt dereferenced address 0x4f.
        self.vm.emu_start(self.base + authority.RETURN_RVA,
                          self.base + 0x2F8BE0, count=10)
        esp = self.vm.reg_read(reg.UC_X86_REG_ESP)
        self.assertEqual(struct.unpack("<I", self.vm.mem_read(esp + 4, 4))[0], packet)

    def test_hook_preserves_all_live_registers_and_stack(self):
        for account in (0x80000003, 0xC0000003):
            self.admit(0, 0, account, 0x8001)
            values = {reg.UC_X86_REG_EAX: 0x12345678, reg.UC_X86_REG_ECX: 0x150000,
                      reg.UC_X86_REG_EDX: 0x160000, reg.UC_X86_REG_ESI: 0x1234,
                      reg.UC_X86_REG_EDI: 0x5678, reg.UC_X86_REG_EBX: self.client,
                      reg.UC_X86_REG_EBP: self.frame, reg.UC_X86_REG_ESP: self.stack}
            for register, value in values.items():
                self.vm.reg_write(register, value)
            self.vm.emu_start(self.base + authority.HOOK_RVA, self.base + authority.RETURN_RVA, count=100)
            self.assertEqual({r: self.vm.reg_read(r) for r in values}, values)

    def test_distinct_accounts_survive_map_insert_result_overwriting_local(self):
        for account in (2, 3, 7, 0x3fffffff):
            self.assertEqual(self.admit(0, 0, 0x80000000 | account)[1], 0x80000000 | account)

    def test_packet_lookup_skips_retired_transport_before_address_compare(self):
        retired = 0x120000
        self.vm.mem_write(retired + 0x14, struct.pack("<H", 0x8001))
        self.vm.mem_write(retired + 0x8228, struct.pack("<I", 0))
        self.vm.reg_write(reg.UC_X86_REG_ESI, retired)
        self.vm.reg_write(reg.UC_X86_REG_EDI, 0x130000)
        self.vm.reg_write(reg.UC_X86_REG_EBX, 0x8001)
        self.vm.emu_start(
            self.base + authority.CONNECTION_LOOKUP_RVA,
            self.base + authority.CONNECTION_LOOKUP_NEXT_RVA,
            count=100,
        )
        self.assertEqual(
            self.vm.reg_read(reg.UC_X86_REG_EIP),
            self.base + authority.CONNECTION_LOOKUP_NEXT_RVA,
        )

    def test_packet_lookup_preserves_displaced_instructions_for_live_transport(self):
        live, packet = 0x120000, 0x130000
        self.vm.mem_write(live + 0x14, struct.pack("<H", 0x8001))
        self.vm.mem_write(live + 0x8228, struct.pack("<I", 4))
        self.vm.mem_write(packet + 0x14, struct.pack("<I", 0x13572468))
        self.vm.reg_write(reg.UC_X86_REG_ESI, live)
        self.vm.reg_write(reg.UC_X86_REG_EDI, packet)
        self.vm.reg_write(reg.UC_X86_REG_EBX, 0x8001)
        self.vm.emu_start(
            self.base + authority.CONNECTION_LOOKUP_RVA,
            self.base + authority.CONNECTION_LOOKUP_RESUME_RVA,
            count=100,
        )
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EAX), packet)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EDX), 0x13572468)
        self.assertEqual(
            self.vm.reg_read(reg.UC_X86_REG_EIP),
            self.base + authority.CONNECTION_LOOKUP_RESUME_RVA,
        )

    def test_packet_lookup_rejects_token_mismatch_before_state_or_string_access(self):
        connection = 0x300000
        self.vm.mem_map(connection, 0x1000)
        self.vm.mem_write(connection + 0x14, struct.pack("<H", 0))
        self.vm.reg_write(reg.UC_X86_REG_ESI, connection)
        self.vm.reg_write(reg.UC_X86_REG_EDI, 0x130000)
        self.vm.reg_write(reg.UC_X86_REG_EBX, 0x8001)
        self.vm.emu_start(
            self.base + authority.CONNECTION_LOOKUP_RVA,
            self.base + authority.CONNECTION_LOOKUP_NEXT_RVA,
            count=100,
        )
        self.assertEqual(
            self.vm.reg_read(reg.UC_X86_REG_EIP),
            self.base + authority.CONNECTION_LOOKUP_NEXT_RVA,
        )

    def allocate(self, token, account, records, clients=(), stop_at_stock=False):
        host = self.client
        connection_id = self.client + 0x1000
        record_address = self.client + 0x2000
        return_address = self.client + 0x3000
        self.vm.mem_write(host + 0x164, struct.pack("<II", record_address, record_address + 12 * len(records)))
        self.vm.mem_write(record_address, b"".join(struct.pack("<IIHBB", *record, 0) for record in records))
        self.vm.mem_write(host + 0x180, struct.pack("<I", clients[0][0] if clients else 0))
        for index, (address, number, identity, state) in enumerate(clients):
            self.vm.mem_write(address + 8, struct.pack("<II", number, identity))
            self.vm.mem_write(address + 0x8228, struct.pack("<I", state))
            self.vm.mem_write(address + 0x8430, struct.pack("<I", clients[index + 1][0] if index + 1 < len(clients) else 0))
        self.vm.mem_write(connection_id, struct.pack("<H", token))
        self.vm.mem_write(
            self.stack,
            struct.pack("<III", return_address, connection_id, account),
        )
        self.vm.reg_write(reg.UC_X86_REG_ECX, host)
        self.vm.reg_write(reg.UC_X86_REG_ESP, self.stack)
        self.vm.emu_start(self.base + authority.ALLOCATOR_CAVE_RVA,
                          self.base + 0x2F1B80 if stop_at_stock else return_address, count=1000)
        return record_address, connection_id

    def test_reclaims_local_number_and_native_lookup_resolves_new_transport(self):
        host, departed, returning = 0x120000, 0x130000, 0x140000
        records = [(0, 0x80000002, 0, 1), (1, 0x80000003, 0, 1)]
        before = b"".join(struct.pack("<IIHBB", *record, 0) for record in records)
        address, _ = self.allocate(0x8001, 0x80000003, records, [
            (host, 0, 0x80000002, 4), (departed, 1, 0x80000003, 0),
            (returning, 0xffffffff, 0x80000003, 1),
        ])
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EAX), 1)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_ESP), self.stack + 12)
        self.assertEqual(bytes(self.vm.mem_read(address, 24)), before)
        self.assertEqual(bytes(self.vm.mem_read(departed + 8, 4)), b"\xff" * 4)
        self.assertEqual(bytes(self.vm.mem_read(host + 8, 8)), struct.pack("<II", 0, 0x80000002))
        self.vm.mem_write(returning + 8, struct.pack("<I", 1))
        self.vm.reg_write(reg.UC_X86_REG_ECX, self.client)
        self.vm.reg_write(reg.UC_X86_REG_ESP, self.stack)
        self.vm.mem_write(self.stack, struct.pack("<II", 0x110000, 1))
        self.vm.emu_start(self.base + 0x2F1AD0, 0x110000, count=100)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EAX), returning)

    def test_reconnect_never_steals_live_or_wrong_account_transport(self):
        for state, identity in [(1, 0x80000003), (4, 0x80000003), (0, 0x80000002)]:
            with self.subTest(state=state, identity=identity):
                _, token_address = self.allocate(0x8001, 0x80000003,
                    [(1, 0x80000003, 0, 1)], [(0x120000, 1, identity, state)], True)
                self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EIP), self.base + 0x2F1B80)
                self.assertEqual(bytes(self.vm.mem_read(token_address, 2)), b"\0\0")
                self.assertEqual(bytes(self.vm.mem_read(0x120008, 4)), struct.pack("<I", 1))

    def test_reconnect_requires_full_record_number_and_account(self):
        for records in ([], [(1, 0x80000002, 0, 1)], [(257, 0x80000003, 0, 1)]):
            with self.subTest(records=records):
                _, token_address = self.allocate(0x8001, 0x80000003, records, stop_at_stock=True)
                self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EIP), self.base + 0x2F1B80)
                self.assertEqual(bytes(self.vm.mem_read(token_address, 2)), b"\0\0")

    def test_duplicate_live_transport_prevents_partial_retirement(self):
        self.allocate(0x8001, 0x80000003, [(1, 0x80000003, 0, 1)], [
            (0x120000, 1, 0x80000003, 0), (0x130000, 1, 0x80000003, 4),
        ], True)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EIP), self.base + 0x2F1B80)
        for address in (0x120008, 0x130008):
            self.assertEqual(bytes(self.vm.mem_read(address, 4)), struct.pack("<I", 1))

    def test_host_zero_and_repeated_reconnects_keep_same_native_number(self):
        for number in (0, 1, 9, 127):
            for cycle in range(3):
                records = [(number, 0x80000003, 0, 1)]
                self.allocate(0x8000 | number, 0x80000003, records, [
                    (0x120000, 0xffffffff, 0x80000003, 0),
                    (0x130000, number, 0x80000003, 0),
                ])
                self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EAX), number, (number, cycle))

    def test_initial_admission_and_nonprivate_tokens_keep_stock_allocation(self):
        for token in (0, 7, 0x7fff, 0x8080, 0xffff):
            _, address = self.allocate(token, 0x80000003, [], stop_at_stock=True)
            self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EIP), self.base + 0x2F1B80)
            self.assertEqual(bytes(self.vm.mem_read(address, 2)), struct.pack("<H", token))

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
        number_offset = pe.get_offset_from_rva(0x333DD)
        self.assertEqual(
            self.game[number_offset:number_offset + 8],
            bytes.fromhex("8B406C3B47087416"),
        )

    def test_stock_game_reconnect_rejects_host_and_accepts_retained_leaver(self):
        self.admit(0, 0, 0xC0000003, 0x8001)
        self.vm.mem_write(self.client + 8, struct.pack("<I", 1))
        pe = pefile.PE(data=self.game)
        base = pe.OPTIONAL_HEADER.ImageBase
        self.vm.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        self.vm.mem_write(base, pe.get_memory_mapped_image())
        node, player = 0x150000, 0x151000
        self.vm.reg_write(reg.UC_X86_REG_EDI, self.client)
        self.vm.reg_write(reg.UC_X86_REG_ESP, self.stack)
        self.vm.mem_write(node + 0x10, struct.pack("<I", player))
        self.vm.mem_write(player + 0x258, struct.pack("<I", 0x80000002))
        self.vm.reg_write(reg.UC_X86_REG_EBX, node)
        self.vm.emu_start(base + 0x333A0, base + 0x33428, count=100)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EIP), base + 0x33428)
        # The next tree entry is the disconnected player's original CPlayer.
        self.vm.mem_write(player + 0x258, struct.pack("<I", 0x80000003))
        self.vm.mem_write(player + 0x6C, struct.pack("<I", 1))
        before = bytes(self.vm.mem_read(player, 0x400))
        # The isolated PE has no linked CRT/IAT. Model only its empty-string
        # constructor; execute the stock account/number predicates themselves.
        self.vm.mem_write(base + 0x2140, bytes.fromhex("c7461400000000c3"))
        self.vm.reg_write(reg.UC_X86_REG_EBX, node)
        self.vm.emu_start(base + 0x333A0, base + 0x33461, count=100)
        self.assertEqual(self.vm.reg_read(reg.UC_X86_REG_EIP), base + 0x33461)
        self.assertEqual(bytes(self.vm.mem_read(player, 0x400)), before)

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

    def test_v19_upgrade_preserves_old_dll_and_rebuilds_current(self):
        from thorgor.patches.engine import _rva_to_file
        baseline = (self.work / "k2.dll.thorgor_v77_baseline").read_bytes()
        legacy = bytearray(baseline)
        code = bytes.fromhex(
            "8b45b8a90000004074078b55e86689531425ffffffbf89430c"
            "83a3cc000000f8f645ef017407838bcc00000007"
        )
        code += authority.jump(authority.CAVE_RVA + len(code), authority.RETURN_RVA)
        old_operations = [
            (authority.MARKER_REJECTION_RVA, b"\x90" * 6),
            (authority.HOOK_RVA, authority.jump(authority.HOOK_RVA, authority.CAVE_RVA) + b"\x90\x90"),
            (authority.CAVE_RVA, code.ljust(0x40, b"\0")),
            (authority.PROMOTION_RVA, b"\x90" * 7),
            (authority.ACCOUNT_RESET_RVA, b"\x90" * 3),
            (0x2F1BAD, bytes.fromhex("3810740b9090")),
        ]
        for rva, replacement in old_operations:
            offset = _rva_to_file(legacy, rva)
            legacy[offset:offset + len(replacement)] = replacement
        old_hash = "FF053A133261FD565B6656AE24F5182AA2423195EA9B77C304128045BBD33A6B"
        self.assertEqual(sha256(legacy), old_hash)
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "k2.dll").write_bytes(legacy)
            (home / "k2.dll.thorgor_stock_3.2.7.1").write_bytes(
                (self.home / "k2.dll.thorgor_stock_3.2.7.1").read_bytes())
            install_k2(home)
            self.assertEqual((home / "k2.dll").read_bytes(), self.image)
            self.assertEqual((home / f"k2.dll.thorgor_before_{old_hash.lower()}").read_bytes(), legacy)

    def test_v20_upgrade_preserves_old_dll_and_rebuilds_v21(self):
        from thorgor.patches.engine import _rva_to_file
        baseline = (self.work / "k2.dll.thorgor_v77_baseline").read_bytes()
        legacy = bytearray(baseline)
        for rva, expected, replacement in authority.operations():
            if rva in (authority.CONNECTION_LOOKUP_RVA, authority.CONNECTION_LOOKUP_CAVE_RVA):
                continue
            offset = _rva_to_file(legacy, rva)
            self.assertEqual(legacy[offset:offset + len(expected)], expected)
            legacy[offset:offset + len(replacement)] = replacement
        old_hash = "660FE63534A41D67AF44D53405FA526C022A649AE9A31327DA2C739A2232F819"
        self.assertEqual(sha256(legacy), old_hash)
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "k2.dll").write_bytes(legacy)
            (home / "k2.dll.thorgor_stock_3.2.7.1").write_bytes(
                (self.home / "k2.dll.thorgor_stock_3.2.7.1").read_bytes())
            install_k2(home)
            self.assertEqual((home / "k2.dll").read_bytes(), self.image)
            self.assertEqual((home / f"k2.dll.thorgor_before_{old_hash.lower()}").read_bytes(), legacy)

    def test_v21_upgrade_preserves_old_dll_and_rebuilds_v22(self):
        from thorgor.patches.engine import _rva_to_file
        baseline = (self.work / "k2.dll.thorgor_v77_baseline").read_bytes()
        legacy = bytearray(baseline)
        for rva, expected, replacement in authority.operations():
            if rva == authority.CONNECTION_LOOKUP_CAVE_RVA:
                old = bytearray(bytes.fromhex("83be2882000000"))
                old.extend(bytes.fromhex("0f84"))
                old.extend(struct.pack(
                    "<i",
                    authority.CONNECTION_LOOKUP_NEXT_RVA
                    - (authority.CONNECTION_LOOKUP_CAVE_RVA + len(old) + 4),
                ))
                old.extend(bytes.fromhex("89f88b5014"))
                old.extend(authority.jump(
                    authority.CONNECTION_LOOKUP_CAVE_RVA + len(old),
                    authority.CONNECTION_LOOKUP_RESUME_RVA,
                ))
                replacement = bytes(old).ljust(0x40, b"\0")
            offset = _rva_to_file(legacy, rva)
            self.assertEqual(legacy[offset:offset + len(expected)], expected)
            legacy[offset:offset + len(replacement)] = replacement
        old_hash = "BA40A63B4F0AA20A93C058A08699A10F9BE3A46CC10AB4DC702AF9C0A79CF5BD"
        self.assertEqual(sha256(legacy), old_hash)
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "k2.dll").write_bytes(legacy)
            (home / "k2.dll.thorgor_stock_3.2.7.1").write_bytes(
                (self.home / "k2.dll.thorgor_stock_3.2.7.1").read_bytes())
            install_k2(home)
            self.assertEqual((home / "k2.dll").read_bytes(), self.image)
            self.assertEqual((home / f"k2.dll.thorgor_before_{old_hash.lower()}").read_bytes(), legacy)
