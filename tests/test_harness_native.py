import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from thorgor.tools.harness_native import await_players, await_slave, bridge_frames
from thorgor.tools.harness_clients import Identity, NativeClient, native_connect_packet
from thorgor.protocols.packet_decoding import parse_connect_c0


class NativeReadinessTests(unittest.TestCase):
    def test_native_bootstrap_ack_and_observed_ready_commands(self):
        with patch("thorgor.tools.harness_clients.socket.socket") as factory:
            connection = factory.return_value
            packets = [bytes.fromhex("000003010000005400")]
            def receive(_size):
                if packets:
                    return packets.pop(0)
                raise TimeoutError()
            connection.recv.side_effect = receive
            client = NativeClient("creator", Identity(1, "cookie", "a" * 40), "key")
            try:
                client.admit()
                self.assertTrue(client.bootstrapped)
                sent = [call.args[0] for call in connection.send.call_args_list]
                self.assertIn(bytes.fromhex("00000501000000"), sent)
                self.assertIn(bytes.fromhex("00000301000000c2c4"), sent)
            finally:
                client.close()
            connection.close.assert_called_once()

    @unittest.skipUnless(os.name == "nt", "requires native Windows inspector imports")
    def test_native_roster_requires_two_distinct_connected_accounts(self):
        clients = []
        for number, status, passing in ((1, 0x40, True), (0, 0x40, False), (1, 0, False)):
            with self.subTest(number=number, status=status):
                players = [
                    {"account_id_low30": 1, "native_client_number": 0, "connection_status": 0x40},
                    {"account_id_low30": 2, "native_client_number": number, "connection_status": status},
                ]
                with patch("thorgor.game_manager.native_match_id.inspect_native_match_id",
                           return_value={"cgame": 1234, "native_match_id": 5}), \
                     patch("thorgor.game_manager.native_match_id.inspect_native_players", return_value=players), \
                     patch("thorgor.tools.harness_native.time.monotonic", side_effect=[0, 0, 21]):
                    if passing:
                        await_players(100, 5, clients, {1, 2}, lambda *args, **kwargs: None)
                    else:
                        with self.assertRaises(TimeoutError):
                            await_players(100, 5, clients, {1, 2}, lambda *args, **kwargs: None)

    def test_native_c0_contains_authentication_and_network_trailer(self):
        identity = Identity(7, "test-cookie", "a" * 40)
        packet = native_connect_packet("creator", identity, 1234, "test-key")
        parsed = parse_connect_c0(packet)
        self.assertEqual((parsed.username, parsed.cookie, parsed.account_id, parsed.host_id),
                         ("creator", "test-cookie", 7, 1234))
        first, second, settings = packet[parsed.account_id_offset + 4:].split(b"\0", 2)
        self.assertEqual(first, identity.auth_hash.encode())
        self.assertEqual(len(second), 40)
        self.assertEqual(settings, bytes.fromhex("000114050000204e000014000000"))

    def test_incomplete_bridge_line_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "work").mkdir()
            path = directory / "work/manager_status_bridge_v42_events.jsonl"
            path.write_bytes(b'{"kind":"real_slave_association"}\n{"kind":')
            self.assertEqual(bridge_frames(directory), [{"kind": "real_slave_association"}])

    def test_synthetic_readiness_cannot_pass(self):
        class Job:
            pid = 100
            def pids(self):
                return {100, 101}

        frames = [{"kind": "control_frame", "connection": "a", "opcode": "0x42",
                   "direction": "MANAGER_TO_SLAVE"}]
        with patch("thorgor.tools.harness_native.bridge_frames", return_value=frames), \
             patch("thorgor.tools.harness_native.time.monotonic", side_effect=[0, 0, 91]), \
             patch("thorgor.tools.harness_native.time.sleep"), \
             patch("thorgor.tools.harness_native.udp_owners") as owners:
            with self.assertRaises(TimeoutError):
                await_slave(Job(), Path("."))
            owners.assert_not_called()

    def test_real_association_wake_and_owned_socket_pass(self):
        class Job:
            pid = 100
            tracked = None
            def pids(self):
                return {100, 101}
            def track(self, pid):
                self.tracked = pid

        job = Job()
        frames = [{"kind": "real_slave_association", "connection": "a"},
                  {"kind": "genuine_manager_wake", "connection": "a"}]
        with patch("thorgor.tools.harness_native.bridge_frames", return_value=frames), \
             patch("thorgor.tools.harness_native.udp_owners", return_value={101, 999}):
            self.assertEqual(await_slave(job, Path(".")), 101)
            self.assertEqual(job.tracked, 101)


@unittest.skipUnless(os.name == "nt", "requires Windows job objects")
class NativeJobTests(unittest.TestCase):
    def test_suspended_launch_preserves_arguments_and_reaps_descendant(self):
        from thorgor.tools.harness_job import NativeJob
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path = directory / "child.json"
            script = (
                "import json,subprocess,sys,time;"
                "from pathlib import Path;"
                "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)']);"
                "Path(sys.argv[1]).write_text(json.dumps([p.pid,sys.argv[2:]]));"
                "time.sleep(120)"
            )
            job = NativeJob([sys.executable, "-c", script, str(path),
                             "-manager", "argument with spaces"], directory, dict(os.environ))
            try:
                deadline = time.monotonic() + 10
                while not path.exists():
                    if time.monotonic() >= deadline:
                        self.fail("owned test process did not start")
                    time.sleep(0.05)
                child, arguments = json.loads(path.read_text())
                self.assertEqual(arguments, ["-manager", "argument with spaces"])
                self.assertIn(child, job.pids())
            finally:
                exits = job.stop()
            self.assertTrue({job.pid, child}.issubset(exits))
            self.assertTrue(all(code != 259 for code in exits.values()))
