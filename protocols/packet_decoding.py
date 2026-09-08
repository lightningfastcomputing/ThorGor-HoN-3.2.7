"""Decode and describe HoN 3.2.7 game datagrams without I/O."""
from __future__ import annotations

import binascii
import re
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectC0:
    product: str
    version: str
    host_id: int
    connection_id: int
    password: str
    username: str
    cookie: str
    ip: str
    match_key: str
    invitation: str
    external_auth: bool
    flag_offset: int


def parse_lobby_create(data: bytes) -> dict[str, str] | None:
    marker = b"\x00map:"
    marker_at = data.find(marker, 7)
    if marker_at < 0:
        return None
    name_start = marker_at
    while name_start > 7 and 0x20 <= data[name_start - 1] <= 0x7E:
        name_start -= 1
    if name_start == marker_at:
        return None
    settings_end = data.find(b"\x00", marker_at + 1)
    if settings_end < 0:
        return None
    try:
        match_name = data[name_start:marker_at].decode("utf-8", errors="strict")
        settings = data[marker_at + 1:settings_end].decode("ascii", errors="strict")
    except UnicodeDecodeError:
        return None
    fields = {key: value for key, value in re.findall(r"([a-z0-9_]+):(\S*)", settings)}
    if not match_name or not fields.get("map"):
        return None
    fields.update(mname=match_name, options=settings)
    return fields


def parse_connect_c0(data: bytes) -> ConnectC0:
    if len(data) < 4 or data[:4] != b"\x00\x00\x01\xc0":
        raise ValueError("not a HoN C0 connection packet")
    cursor = 4

    def read_cstring(label: str) -> str:
        nonlocal cursor
        end = data.find(b"\x00", cursor)
        if end < 0:
            raise ValueError(f"unterminated {label}")
        try:
            value = data[cursor:end].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError(f"invalid UTF-8 in {label}") from exc
        cursor = end + 1
        return value

    product = read_cstring("product")
    version = read_cstring("version")
    if cursor + 6 > len(data):
        raise ValueError("truncated host or connection id")
    host_id, connection_id = struct.unpack_from("<IH", data, cursor)
    cursor += 6
    password = read_cstring("password")
    username = read_cstring("username")
    cookie = read_cstring("cookie")
    ip = read_cstring("ip")
    match_key = read_cstring("match key")
    invitation = read_cstring("invitation")
    if cursor >= len(data):
        raise ValueError("missing external-auth flag")
    flag_offset = cursor
    external_auth = bool(data[cursor] & 1)
    if product != "Heroes of Newerth" or version != "3.2.7.1":
        raise ValueError(f"unsupported product/version: {product!r} {version!r}")
    if not username or not cookie:
        raise ValueError("username and cookie are required")
    return ConnectC0(product, version, host_id, connection_id, password, username,
                     cookie, ip, match_key, invitation, external_auth, flag_offset)


def format_packet(data: bytes) -> str:
    hex_text = binascii.hexlify(data).decode("ascii")
    grouped = " ".join(hex_text[i:i + 2] for i in range(0, len(hex_text), 2))
    ascii_text = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in data)
    return f"len={len(data)} hex={grouped} ascii={ascii_text}"


def classify_packet(data: bytes) -> str:
    if len(data) >= 4 and data[:3] == b"\x00\x00\x01":
        command = data[3]
        return f"cmd=0x{command:02x}({chr(command) if 32 <= command <= 126 else '?'})"
    return "cmd=raw"


def extract_cpacket_strings(data: bytes) -> list[str]:
    chunks: list[str] = []
    current = bytearray()
    for byte in data:
        if byte:
            current.append(byte)
            continue
        if current:
            try:
                text = current.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                text = ""
            if text and all(31 < ord(ch) < 127 for ch in text):
                chunks.append(text)
        current.clear()
    return chunks


def describe_special_packet(data: bytes) -> str:
    if len(data) < 4 or data[:3] != b"\x00\x00\x01":
        return ""
    command = data[3]
    strings = extract_cpacket_strings(data[4:])
    if command == 0xC0:
        labels = ("product", "version", "username", "cookie", "ip", "acc_key",
                  "acc_key_short_hash", "acc_key_hash")
        values = [f"{label}={value!r}" for label, value in zip(labels, strings)]
        values.extend(f"extra_{index}={value!r}" for index, value in
                      enumerate(strings[len(labels):], start=1))
        return "CONNECT_C0 " + " ".join(values)
    if command == 0x51 and strings:
        return "SERVER_Q1 " + " ".join(
            f"text_{index}={value!r}" for index, value in enumerate(strings, start=1)
        )
    if command in {0xC3, 0xC9}:
        return f"CONTROL_{command:02X}"
    return ""
