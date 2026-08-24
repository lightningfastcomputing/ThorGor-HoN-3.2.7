import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from thorgor.protocols.game_protocol import build_proxy_challenge, parse_lobby_create


ROOT = Path(__file__).resolve().parents[1]


def free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


class UdpMulticlientRoutingTests(unittest.TestCase):
    def test_compel_proxy_challenge_has_exact_native_layout(self):
        packet = build_proxy_challenge(1, 2)

        self.assertEqual(len(packet), 58)
        self.assertEqual(packet[:40], bytes(40))
        self.assertEqual(packet[40:44], b"\xff\xff\x40\x00")
        self.assertEqual(packet[44:48], b"\x01\x00\x00\x00")
        self.assertEqual(packet[48:54], b"\x3c\x00\xff\xff\xff\xff")
        self.assertEqual(packet[54:58], b"\x02\x00\x00\x00")

    def test_real_3271_create_packet_extracts_name_and_rules(self):
        packet = (
            b"\x00\x00\x03\xd4\x01\x00\x00\xc4\xc8\x1a"
            b"asd\x00map:caldavar region: teamsize:5 minpsr:0 maxpsr:0 "
            b"mode:normal casual:true nostats:true \x00"
        )

        lobby = parse_lobby_create(packet)

        self.assertIsNotNone(lobby)
        self.assertEqual(lobby["mname"], "asd")
        self.assertEqual(lobby["map"], "caldavar")
        self.assertEqual(lobby["teamsize"], "5")
        self.assertEqual(lobby["casual"], "true")

    def test_two_clients_use_unique_loopback_identities_and_receive_own_responses(self):
        listen_port = free_udp_port()
        target_port = free_udp_port()
        target = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        target.bind(("127.0.0.1", target_port))
        target.settimeout(3.0)
        observed_upstreams = []
        target_error = []

        def echo_after_both_arrive():
            try:
                received = [target.recvfrom(4096), target.recvfrom(4096)]
                observed_upstreams.extend(address for unused, address in received)
                for payload, address in received:
                    target.sendto(b"reply:" + payload, address)
            except Exception as exc:  # surfaced in the test thread
                target_error.append(exc)

        echo_thread = threading.Thread(target=echo_after_both_arrive, daemon=True)
        echo_thread.start()

        with tempfile.TemporaryDirectory() as temp_dir:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "thorgor.protocols.game_protocol",
                    "--listen-host",
                    "127.0.0.1",
                    "--listen-port",
                    str(listen_port),
                    "--target-host",
                    "127.0.0.1",
                    "--target-port",
                    str(target_port),
                    "--log-file",
                    str(Path(temp_dir) / "shim.log"),
                    "--max-client-routes",
                    "10",
                    "--unique-loopback-sources",
                ],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            client_one = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_two = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                client_one.bind(("127.0.0.1", 0))
                client_two.bind(("127.0.0.1", 0))
                client_one.settimeout(3.0)
                client_two.settimeout(3.0)
                time.sleep(0.25)

                bridge = ("127.0.0.1", listen_port)
                client_one.sendto(b"client-one", bridge)
                client_two.sendto(b"client-two", bridge)

                self.assertEqual(client_one.recvfrom(4096)[0], b"reply:client-one")
                self.assertEqual(client_two.recvfrom(4096)[0], b"reply:client-two")
                echo_thread.join(timeout=3.0)
                self.assertFalse(target_error, target_error)
                self.assertEqual(len(observed_upstreams), 2)
                self.assertNotEqual(observed_upstreams[0][0], observed_upstreams[1][0])
                self.assertTrue(all(address[0].startswith("127.0.0.") for address in observed_upstreams))
                self.assertNotEqual(observed_upstreams[0][1], observed_upstreams[1][1])
            finally:
                client_one.close()
                client_two.close()
                process.terminate()
                try:
                    process.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3.0)
                target.close()


if __name__ == "__main__":
    unittest.main()
