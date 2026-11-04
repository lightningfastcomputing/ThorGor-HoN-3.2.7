"""Protocol clients for the loopback backend scenarios."""
from __future__ import annotations

from dataclasses import dataclass
from http.client import HTTPConnection
import hashlib
import re
import secrets
import socket
import struct
import time
import zlib
from urllib.parse import urlencode

from thorgor.chat.protocol import cstr, encode_packet
from thorgor.master.auth import (
    CHAT_SERVER_AUTHENTICATION_SALT, G, H, N, hon_password, pad_num, xor_bytes,
)
from thorgor.protocols.php_wire import parse_php_string_field


@dataclass(frozen=True, repr=False)
class Identity:
    account_id: int
    cookie: str
    auth_hash: str


def post(http_port: int, path: str = "/", **fields: str) -> bytes:
    connection = HTTPConnection("127.0.0.1", http_port, timeout=3)
    try:
        connection.request("POST", path, urlencode(fields),
                           {"Content-Type": "application/x-www-form-urlencoded"})
        response = connection.getresponse()
        wire = response.read(65537)
        if response.status != 200 or len(wire) > 65536:
            raise ValueError("unexpected master HTTP response")
        return wire
    finally:
        connection.close()


def login(port: int, username: str, password: str, *, reject: bool = False) -> Identity | None:
    private = secrets.randbits(256) | (1 << 255)
    public = pow(G, private, N)
    challenge = post(port, f="pre_auth", login=username, A=f"{public:0512x}")
    salt = int(parse_php_string_field(challenge, "salt"), 16)
    server_public = int(parse_php_string_field(challenge, "B"), 16)
    if not 0 < server_public < N:
        raise ValueError("invalid SRP server public value")
    salt2 = parse_php_string_field(challenge, "salt2")
    transformed = hon_password(password, salt2, "pre-md5")
    x = int.from_bytes(H(pad_num(salt), H(f"{username}:{transformed}".encode())), "big")
    k = int.from_bytes(H(pad_num(N), pad_num(G)), "big")
    u = int.from_bytes(H(pad_num(public), pad_num(server_public)), "big")
    shared = pow((server_public - k * pow(G, x, N)) % N, private + u * x, N)
    key = H(pad_num(shared))
    proof = H(xor_bytes(H(pad_num(N)), H(pad_num(G))), H(username.encode()),
              pad_num(salt), pad_num(public), pad_num(server_public), key)
    result = post(port, f="srpAuth", login=username, proof=proof.hex())
    auth = parse_php_string_field(result, "auth")
    if reject:
        if auth != "SRP proof mismatch":
            raise ValueError("master did not reject the incorrect password")
        return None
    expected = H(pad_num(public), proof, key).hex()
    if auth != "Authorized" or parse_php_string_field(result, "proof") != expected:
        raise ValueError("master login or SRP server proof failed")
    account = re.search(rb's:10:"account_id";i:([1-9][0-9]*);', result)
    if account is None or parse_php_string_field(result, "nickname") != username:
        raise ValueError("master returned an unexpected identity")
    return Identity(int(account[1]), parse_php_string_field(result, "cookie"),
                    parse_php_string_field(result, "auth_hash"))


def chat_auth(connection: socket.socket, identity: Identity, cookie: str) -> None:
    payload = (struct.pack("<I", identity.account_id) + cstr(cookie) + cstr("127.0.0.1")
               + cstr(identity.auth_hash) + struct.pack("<II", 47, 0))
    connection.sendall(encode_packet(0x0C00, payload))


def expect_chat_acceptance(connection: socket.socket) -> None:
    expected = encode_packet(0x1C00)
    received = bytearray()
    deadline = time.monotonic() + 3
    while len(received) < len(expected):
        connection.settimeout(max(0, deadline - time.monotonic()))
        chunk = connection.recv(len(expected) - len(received))
        if not chunk:
            break
        received.extend(chunk)
    if received != expected:
        raise ValueError("chat did not send the expected AUTH_ACCEPTED frame")


def native_connect_packet(username: str, identity: Identity, host_id: int, match_key: str) -> bytes:
    key_hash = hashlib.sha1(
        (match_key + identity.cookie + CHAT_SERVER_AUTHENTICATION_SALT).encode()
    ).hexdigest() if match_key else ""
    # Both preserved live C0 traces contain this 14-byte network-settings tail.
    settings = bytes.fromhex("000114050000204e000014000000")
    return (b"\0\0\1\xc0" + cstr("Heroes of Newerth") + cstr("3.2.7.1")
            + struct.pack("<IH", host_id, 0)
            + b"".join(cstr(value) for value in
                       ("", username, identity.cookie, "127.0.0.1", match_key, ""))
            + b"\0" + struct.pack("<I", identity.account_id)
            + cstr(identity.auth_hash) + cstr(key_hash) + settings)


class NativeClient:
    """Independent admission, reliable controls, and snapshot acknowledgment state."""
    def __init__(self, username: str, identity: Identity, match_key: str):
        self.account_id = identity.account_id
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(("127.0.0.1", 0))
            self.socket.connect(("127.0.0.1", 11236))
            self.socket.settimeout(0.01)
            self.endpoint = self.socket.getsockname()
        except OSError:
            self.socket.close()
            raise
        self.request = native_connect_packet(username, identity, secrets.randbits(32) or 1, match_key)
        self.sent = 0
        self.received = 0
        self.native_number = None
        self.packet_types = {}
        self.bootstrapped = False
        self.next_sequence = 1
        self.pending = {}
        self.server_sequences = set()
        self.unique_reliable = 0
        self.packet_shapes = {}
        self.next_heartbeat = 0
        self.snapshots_enabled = False
        self.next_snapshot_ack = 0
        self.snapshot_frames = 0
        self.snapshot_packets = 0
        self.snapshot_complete = 0
        self.last_snapshot_frame = None
        self.snapshot_errors = 0
        self.active = True
        from thorgor.protocols.native_snapshot import SnapshotReceiver
        self.snapshot_receiver = SnapshotReceiver()

    def send(self, data):
        self.socket.send(data)
        self.sent += 1

    def reliable(self, payload):
        sequence = self.next_sequence
        self.next_sequence += 1
        packet = b"\0\0\3" + struct.pack("<I", sequence) + payload
        self.pending[sequence] = {"packet": packet, "sent_at": time.monotonic()}
        self.send(packet)
        return sequence

    def game_command(self, command, payload=b""):
        return self.reliable(bytes((0xC8, command)) + payload)

    def receive(self, data):
        from thorgor.protocols.game_protocol import parse_server_client_assignment
        self.received += 1
        kind = f"type_{data[2]:02x}" if len(data) >= 3 else "short"
        command = None
        if len(data) >= 4 and data[2] == 1:
            command = data[3]
        if len(data) >= 8 and data[2] == 3:
            command = data[7]
            sequence = struct.unpack_from("<I", data, 3)[0]
            self.send(data[:2] + b"\x05" + data[3:7])
            if sequence not in self.server_sequences:
                self.server_sequences.add(sequence)
                self.unique_reliable += 1
            if command == 0x54:
                self.bootstrapped = True
        if command is not None:
            kind += f"_command_{command:02x}"
        if command in range(0x5A, 0x5F):
            self.snapshot_packets += 1
            offset = 7 if data[2] == 3 else 3
            try:
                frame = self.snapshot_receiver.receive(data[offset:])
            except (ValueError, zlib.error):
                self.snapshot_errors += 1
            else:
                if frame is not None:
                    self.snapshot_complete += 1
                if frame is not None and (self.last_snapshot_frame is None or
                        0 < (frame - self.last_snapshot_frame) & 0xFFFFFFFF < 0x80000000):
                    self.snapshot_frames += 1
                    self.last_snapshot_frame = frame
        self.packet_types[kind] = self.packet_types.get(kind, 0) + 1
        shape = (kind, len(data))
        if len(self.packet_shapes) < 64 or shape in self.packet_shapes:
            self.packet_shapes[shape] = data[:8].hex()
        if len(data) >= 7 and data[2] == 5:
            self.pending.pop(struct.unpack_from("<I", data, 3)[0], None)
        assigned = parse_server_client_assignment(data)
        if assigned is not None:
            self.native_number = assigned
        return command

    def poll(self):
        if not self.active:
            return None
        now = time.monotonic()
        if now >= self.next_heartbeat:
            self.send(b"\0\0\1\xc9")
            self.next_heartbeat = now + 0.25
        if self.snapshots_enabled and now >= self.next_snapshot_ack:
            frame = self.last_snapshot_frame
            self.send(b"\0\0\1\xc7" + struct.pack("<HI", 32, 0xFFFFFFFF if frame is None else frame))
            self.next_snapshot_ack = now + 0.05
        for pending in self.pending.values():
            if now - pending["sent_at"] >= 1:
                self.send(pending["packet"])
                pending["sent_at"] = now
        command = None
        for _ in range(128):
            try:
                data = self.socket.recv(65535)
            except TimeoutError:
                break
            command = self.receive(data)
        return command

    def finish_loading(self):
        self.reliable(b"\xc5")
        self.snapshots_enabled = True

    def disconnect(self):
        self.send(b"\0\0\1\xc3")
        self.active = False

    def admit(self, peers=()):
        deadline = time.monotonic() + 10
        next_request = 0
        while time.monotonic() < deadline:
            if time.monotonic() >= next_request:
                self.send(self.request)
                next_request = time.monotonic() + 1
            self.poll()
            for peer in peers:
                peer.poll()
            if self.bootstrapped:
                self.reliable(b"\xc2\xc4")
                self.poll()
                return
        raise TimeoutError("native slave did not bootstrap the simulated client")

    def close(self):
        self.socket.close()
