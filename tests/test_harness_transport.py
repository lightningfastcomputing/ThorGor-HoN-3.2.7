import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from thorgor.tools.harness_native import record_proxy
from thorgor.tools.harness_transport import read_endpoint, read_transport


class Memory:
    def __init__(self):
        self.bytes = {}

    def put(self, address, value):
        for offset, byte in enumerate(struct.pack("<I", value)):
            self.bytes[address + offset] = byte

    def read_u8(self, address):
        return self.bytes.get(address, 0)

    def read_u32(self, address):
        return int.from_bytes(bytes(self.read_u8(address + n) for n in range(4)), "little")


class TransportTests(unittest.TestCase):
    def test_registry_loss_does_not_hide_advancing_generated_snapshot(self):
        memory = Memory()
        base, host, server, pool = 0x15000000, 0x10000, 0x20000, 0x30000
        for address, value in {
            base + 0x8D82CC: host, host + 0x78: server,
            server + 0x180: 0, server + 0x108: 3000, server + 0x118: 150000,
            server + 0x128: 0x40000, server + 0x12C: 0x40004,
            server + 0x134: 0, 0x40000: 2, base + 0x8DBFE8: pool,
            pool + 2 * 0x84: 1, pool + 2 * 0x84 + 4: 2999,
            pool + 2 * 0x84 + 12: 150000,
        }.items():
            memory.put(address, value)
        state = read_transport(memory, base)
        self.assertEqual(state["clients"], [])
        self.assertEqual(state["generated_snapshot"],
                         {"handle": 2, "valid": True, "frame": 2999, "engine_time": 150000})

    def test_registry_cycle_fails_instead_of_hanging(self):
        memory = Memory()
        memory.put(0x8D82CC, 0x10000)
        memory.put(0x10078, 0x20000)
        memory.put(0x20180, 0x30000)
        memory.put(0x30000 + 0x8430, 0x30000)
        with patch("thorgor.tools.harness_transport.read_endpoint", return_value=["127.0.0.3", 1234]):
            with self.assertRaisesRegex(ValueError, "cycle"):
                read_transport(memory, 0)

    def test_native_endpoint_is_bounded_and_parsed_as_an_address(self):
        memory = Memory()
        connection, string = 0x10000, 0x101AC
        memory.put(string + 0x14, 3)
        memory.put(string + 0x18, 7)
        for offset, byte in enumerate("::1".encode("utf-16-le")):
            memory.bytes[string + 4 + offset] = byte
        memory.put(connection + 0x1E4, 11235)
        self.assertEqual(read_endpoint(memory, connection), ["::1", 11235])
        memory.put(string + 0x14, 1000)
        with self.assertRaises(ValueError):
            read_endpoint(memory, connection)

    def test_proxy_evidence_keeps_distinct_route_windows_without_raw_packets(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "work").mkdir()
            (directory / "work/hon_udp_shim_public_list.log").write_text(
                "2026-11-04 10:00:00 | ROUTE_OPEN client=127.0.0.1:50001 upstream=127.0.0.3:50002 target=127.0.0.1:11235 routes=2\n"
                "2026-11-04 10:00:01 | ROUTE_STATS client=127.0.0.1:50001 user='joiner' upstream_port=50002 to_server=20pkt/200B from_server=0pkt/0B\n"
                "2026-11-04 10:00:01 | ROUTE_STATS client=127.0.0.1:50003 user='creator' upstream_port=50004 to_server=0pkt/0B from_server=1pkt/10B\n"
                "raw packet cookie=must-not-export\n")
            events = []
            record_proxy(directory, lambda name, **fields: events.append((name, fields)))
            evidence = dict(events)["native_proxy_route_windows"]
            self.assertEqual([sample["from_server"] for sample in evidence["samples"]], [0, 1])
            self.assertEqual(evidence["routes"][0][1], "127.0.0.3:50002")
            self.assertNotIn("must-not-export", str(events))
