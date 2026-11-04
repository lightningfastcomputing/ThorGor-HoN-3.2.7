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


def post(port: int, path: str = "/", **fields: str) -> bytes:
    connection = HTTPConnection("127.0.0.1", port, timeout=3)
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
    """A bounded C0 admission probe. Gameplay state handling is a separate layer."""
    def __init__(self, username: str, identity: Identity, match_key: str):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(("127.0.0.1", 0))
            self.socket.connect(("127.0.0.1", 11236))
            self.socket.settimeout(0.25)
        except OSError:
            self.socket.close()
            raise
        self.request = native_connect_packet(username, identity, secrets.randbits(32) or 1, match_key)
        self.sent = 0
        self.received = 0
        self.native_number = None
        self.packet_types = {}
        self.bootstrapped = False
        self.ready_pending = False
        self.next_ready = 0
        self.next_heartbeat = 0

    def send(self, data):
        self.socket.send(data)
        self.sent += 1

    def poll(self):
        from thorgor.protocols.game_protocol import parse_server_client_assignment
        now = time.monotonic()
        if now >= self.next_heartbeat:
            self.send(b"\0\0\1\xc9")
            self.next_heartbeat = now + 0.25
        if self.ready_pending and now >= self.next_ready:
            self.send(b"\0\0\3" + struct.pack("<I", 1) + b"\xc2\xc4")
            self.next_ready = now + 1
        try:
            data = self.socket.recv(65535)
        except TimeoutError:
            return None
        self.received += 1
        kind = f"type_{data[2]:02x}" if len(data) >= 3 else "short"
        command = None
        if len(data) >= 4 and data[2] == 1:
            command = data[3]
        if len(data) >= 8 and data[2] == 3:
            command = data[7]
            self.send(data[:2] + b"\x05" + data[3:7])
        if command is not None:
            kind += f"_command_{command:02x}"
        self.packet_types[kind] = self.packet_types.get(kind, 0) + 1
        if len(data) >= 7 and data[2] == 5 and struct.unpack_from("<I", data, 3)[0] == 1:
            self.ready_pending = False
        assigned = parse_server_client_assignment(data)
        if assigned is not None:
            self.native_number = assigned
        return command

    def admit(self):
        deadline = time.monotonic() + 10
        next_request = 0
        while time.monotonic() < deadline:
            if time.monotonic() >= next_request:
                self.send(self.request)
                next_request = time.monotonic() + 1
            if self.poll() == 0x54:
                self.bootstrapped = True
                self.ready_pending = True
                self.next_ready = 0
                self.poll()
                return
        raise TimeoutError("native slave did not bootstrap the simulated client")

    def close(self):
        self.socket.close()
