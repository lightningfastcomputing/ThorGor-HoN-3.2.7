"""Protocol clients for the loopback backend scenarios."""
from __future__ import annotations

from dataclasses import dataclass
from http.client import HTTPConnection
import re
import secrets
import socket
import struct
import time
from urllib.parse import urlencode

from thorgor.chat.protocol import cstr, encode_packet
from thorgor.master.auth import G, H, N, hon_password, pad_num, xor_bytes
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
