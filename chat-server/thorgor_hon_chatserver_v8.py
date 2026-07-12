#!/usr/bin/env python3
"""
ThorGor HoN LAN Chat Server v8
Corrected for HoN 3.2.7.1 / chat protocol 47.

Wire framing observed from the real client:
    uint16_le bytes_after_length
    uint16_le command
    payload...

Example captured AUTH_INFO:
    69 00 | 00 0c | ...  (0x69 bytes follow the length field)

Features:
- Correct auth framing and HON_SC_AUTH_ACCEPTED
- Validates the local master-issued account id/cookie by default
- Ping/pong keepalive
- Multi-client LAN registry
- Basic join-channel and channel-message support
- Full packet logging/capture for unsupported operations
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import socket
import socketserver
import struct
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

APP_NAME = "ThorGor HoN LAN Chat Server v8"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 11031
DEFAULT_NICK = "Guest"
ACCOUNT_DB_PATH: Path | None = None

# 16-bit special commands
HON_CS_AUTH_INFO = 0x0C00
HON_SC_AUTH_ACCEPTED = 0x1C00
HON_SC_PING = 0x2A00
HON_CS_PONG = 0x2A01

# Normal 8/16-bit IDs on the same wire command field
HON_CS_CHANNEL_MSG = 0x03
HON_SC_CHANNEL_MSG = 0x03
HON_SC_STATUS_UPDATE = 0x66
HON_SC_CHANGED_CHANNEL = 0x04
HON_SC_JOINED_CHANNEL = 0x05
HON_SC_LEFT_CHANNEL = 0x06
HON_CS_WHISPER = 0x08
HON_SC_WHISPER = 0x08
HON_CS_JOIN_CHANNEL = 0x1E
HON_CS_LEAVE_CHANNEL = 0x22

BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = BASE_DIR / "thorgor_chat_v8.log"
CAPTURE_DIR = BASE_DIR / "thorgor_chat_v8_captures"
CAPTURE_DIR.mkdir(exist_ok=True)
LOG_LOCK = threading.Lock()


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]


def log(msg: str) -> None:
    line = f"{stamp()} | {msg}"
    with LOG_LOCK:
        print(line, flush=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def cstr(text: str) -> bytes:
    return text.encode("utf-8", errors="replace") + b"\x00"


def read_cstr(data: bytes, offset: int) -> tuple[str, int]:
    end = data.find(b"\x00", offset)
    if end < 0:
        raise ValueError("unterminated string")
    return data[offset:end].decode("utf-8", errors="replace"), end + 1


def save_capture(peer: str, direction: str, data: bytes, **extra) -> None:
    now = datetime.now()
    record = {
        "timestamp": now.isoformat(timespec="milliseconds"),
        "peer": peer,
        "direction": direction,
        "length": len(data),
        "hex": data.hex(),
        "ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in data),
        **extra,
    }
    name = now.strftime("%Y%m%d_%H%M%S_%f") + f"_{direction}.json"
    (CAPTURE_DIR / name).write_text(json.dumps(record, indent=2), encoding="utf-8")


def encode_packet(command: int, payload: bytes = b"") -> bytes:
    # HoN 3.2.7.1 uses the same framing in both directions:
    # the uint16 length counts bytes AFTER the two-byte length field.
    #
    # Empty packet example:
    #   02 00 | 00 1c
    #
    # The earlier 04 00 form appeared to "connect" only because the client
    # waited for two bytes from the following ping to complete the packet.
    body = struct.pack("<H", command) + payload
    return struct.pack("<H", len(body)) + body


def extract_packet(buffer: bytes):
    if len(buffer) < 2:
        return None
    following = struct.unpack_from("<H", buffer, 0)[0]
    total = 2 + following
    if following < 2 or total > 1024 * 1024:
        raise ValueError(f"invalid packet length {following}")
    if len(buffer) < total:
        return None
    command = struct.unpack_from("<H", buffer, 2)[0]
    payload = buffer[4:total]
    return total, command, payload, buffer[:total]


def parse_auth(payload: bytes) -> dict:
    """
    Parse only the stable fields needed for local authentication.

    HoN 3.2.7.1 protocol 47 has a short platform/version tail whose exact
    structure differs from newer public documentation. Earlier builds tried
    to force that tail into newer fields and intermittently raised
    "unterminated string".

    Stable observed layout:
        uint32 account_id
        cstring cookie
        cstring ip
        cstring auth_hash
        uint32 protocol
        uint32 client_version_raw
        remaining platform bytes (kept raw)
    """
    o = 0
    if len(payload) < 4:
        raise ValueError("AUTH_INFO payload too short")

    account_id = struct.unpack_from("<I", payload, o)[0]
    o += 4
    cookie, o = read_cstr(payload, o)
    ip, o = read_cstr(payload, o)
    auth_hash, o = read_cstr(payload, o)

    protocol = None
    client_version = None

    if len(payload) >= o + 4:
        protocol = struct.unpack_from("<I", payload, o)[0]
        o += 4

    if len(payload) >= o + 4:
        client_version = struct.unpack_from("<I", payload, o)[0]
        o += 4

    tail = payload[o:]
    printable_tail = "".join(chr(b) if 32 <= b < 127 else "." for b in tail)

    return {
        "account_id": account_id,
        "cookie": cookie,
        "ip": ip,
        "auth_hash": auth_hash,
        "protocol": protocol,
        "client_version_raw": client_version,
        "platform_tail_hex": tail.hex(),
        "platform_tail_ascii": printable_tail,
    }




@dataclass(frozen=True)
class AccountRecord:
    account_id: int
    username: str
    nickname: str
    enabled: bool


def discover_account_db(explicit: str | None = None) -> Path:
    """Resolve the v24 master server SQLite database without guessing silently."""
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Account database not found: {path}")
        return path

    env_path = os.environ.get("THORGOR_ACCOUNT_DB")
    if env_path:
        path = Path(env_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"THORGOR_ACCOUNT_DB does not exist: {path}")
        return path

    roots = [BASE_DIR, BASE_DIR.parent, BASE_DIR.parent.parent, Path.cwd()]
    candidates: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            root = root.resolve()
        except OSError:
            continue
        direct = root / "thorgor_accounts.db"
        if direct.is_file() and direct not in seen:
            seen.add(direct)
            candidates.append(direct)
        try:
            for child in root.iterdir():
                if child.is_dir():
                    candidate = child / "thorgor_accounts.db"
                    if candidate.is_file() and candidate not in seen:
                        seen.add(candidate)
                        candidates.append(candidate)
        except OSError:
            pass

    if not candidates:
        raise FileNotFoundError(
            "Could not find thorgor_accounts.db. Start with --db C:\\path\\to\\thorgor_accounts.db "
            "or set THORGOR_ACCOUNT_DB."
        )
    if len(candidates) > 1:
        listing = "\n  ".join(str(p) for p in candidates)
        raise RuntimeError(
            "Multiple account databases found; select the same one used by the master server with --db:\n  " + listing
        )
    return candidates[0]


def load_account(account_id: int) -> AccountRecord | None:
    if ACCOUNT_DB_PATH is None:
        raise RuntimeError("Account database is not configured")
    with sqlite3.connect(ACCOUNT_DB_PATH, timeout=5) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT account_id, username, nickname, enabled FROM accounts WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    if row is None:
        return None
    return AccountRecord(
        account_id=int(row["account_id"]),
        username=str(row["username"]),
        nickname=str(row["nickname"]),
        enabled=bool(row["enabled"]),
    )


def expected_cookie(account: AccountRecord) -> str:
    return f"THORGOR_LOCAL_COOKIE_{account.account_id:08d}"


def expected_auth_hash(account: AccountRecord) -> str:
    material = f"THORGOR_LOCAL_AUTH:{account.account_id}:{account.username}".encode("utf-8")
    return hashlib.sha1(material).hexdigest()


@dataclass
class ClientState:
    handler: "ChatConnection"
    account_id: int = 0
    nickname: str = DEFAULT_NICK
    channel: Optional[str] = None
    chat_id: int = 0


class ChatWorld:
    def __init__(self):
        self.lock = threading.RLock()
        self.clients: dict[int, ClientState] = {}
        self.next_chat_id = 1000
        self.channels: dict[str, set[int]] = {}
        self.channel_ids: dict[str, int] = {}

    def register(self, state: ClientState):
        with self.lock:
            self.clients[id(state.handler)] = state

    def unregister(self, state: ClientState):
        with self.lock:
            if state.channel:
                members = self.channels.get(state.channel, set())
                members.discard(id(state.handler))
                if not members:
                    self.channels.pop(state.channel, None)
                    self.channel_ids.pop(state.channel, None)
            self.clients.pop(id(state.handler), None)

    def join(self, state: ClientState, channel: str):
        channel = channel or "ThorGor"
        with self.lock:
            if state.channel:
                self.channels.get(state.channel, set()).discard(id(state.handler))
            channel_id = self.channel_ids.get(channel)
            if channel_id is None:
                channel_id = self.next_chat_id
                self.next_chat_id += 1
                self.channel_ids[channel] = channel_id
            state.channel = channel
            state.chat_id = channel_id
            member_ids = self.channels.setdefault(channel, set())
            existing = [self.clients[k] for k in member_ids if k in self.clients]
            member_ids.add(id(state.handler))
            members = [self.clients[k] for k in member_ids if k in self.clients]
        return existing, members, channel_id

    def channel_members(self, channel: str):
        with self.lock:
            return [self.clients[k] for k in self.channels.get(channel, set()) if k in self.clients]


WORLD = ChatWorld()


class ChatConnection(socketserver.BaseRequestHandler):
    def setup(self):
        self.peer = f"{self.client_address[0]}:{self.client_address[1]}"
        self.buffer = b""
        self.send_lock = threading.Lock()
        self.stop = threading.Event()
        self.state = ClientState(self)
        self.authed = False
        self.request.settimeout(1.0)
        log(f"CONNECT | {self.peer}")

    def finish(self):
        self.stop.set()
        WORLD.unregister(self.state)
        log(f"DISCONNECT | {self.peer}")

    def send_packet(self, command: int, payload: bytes = b""):
        frame = encode_packet(command, payload)
        with self.send_lock:
            self.request.sendall(frame)
        save_capture(self.peer, "server_to_client", frame,
                     command=f"0x{command:04X}", payload_length=len(payload))
        log(f"TX | {self.peer} | cmd=0x{command:04X} payload={len(payload)} total={len(frame)}")

    def heartbeat(self):
        if self.stop.wait(5):
            return
        while not self.stop.is_set():
            try:
                self.send_packet(HON_SC_PING)
            except OSError:
                return
            if self.stop.wait(15):
                return

    def auth(self, payload: bytes):
        try:
            info = parse_auth(payload)
        except Exception as exc:
            log(f"AUTH PARSE ERROR | {self.peer} | {exc} | payload={payload.hex()}")
            return

        log("AUTH INFO | " + self.peer + " | " + json.dumps(info, sort_keys=True))

        account = load_account(info["account_id"])
        if account is None:
            log(f"AUTH REJECTED LOCALLY | {self.peer} | unknown account_id={info['account_id']}")
            return
        if not account.enabled:
            log(f"AUTH REJECTED LOCALLY | {self.peer} | disabled account={account.username!r}")
            return

        cookie_ok = info["cookie"] == expected_cookie(account)
        auth_hash_ok = info["auth_hash"].lower() == expected_auth_hash(account).lower()
        if not cookie_ok or not auth_hash_ok:
            log(
                f"AUTH REJECTED LOCALLY | {self.peer} | identity mismatch "
                f"account={account.username!r} cookie_ok={cookie_ok} auth_hash_ok={auth_hash_ok}"
            )
            return

        self.state.account_id = account.account_id
        self.state.nickname = account.nickname
        self.authed = True
        WORLD.register(self.state)

        # Empty payload is the documented AUTH_ACCEPTED form.
        # Correct bytes are: 02 00 00 1c
        self.send_packet(HON_SC_AUTH_ACCEPTED)
        log(f"AUTH ACCEPTED | {self.peer} | account={account.username!r} nickname={account.nickname!r} protocol={info['protocol']}")
        threading.Thread(target=self.heartbeat, daemon=True).start()

    def join_channel(self, payload: bytes):
        try:
            channel, _ = read_cstr(payload, 0)
        except Exception:
            channel = "ThorGor"

        existing, members, channel_id = WORLD.join(self.state, channel)
        log(f"JOIN CHANNEL | {self.peer} | {channel!r} channel_id={channel_id} members={len(members)}")

        # HoN 3.2.7.1 packet 0x04 is a COMPLETE channel snapshot:
        #
        #   WString channel_name
        #   uint32  channel_id
        #   byte    channel_flags
        #   WString topic/message
        #   uint32  auxiliary_entry_count
        #   repeat auxiliary_entry_count:
        #       uint32 value
        #       byte   value
        #   uint32  member_count
        #   repeat member_count:
        #       WString nickname
        #       uint32  account_id
        #       byte    status_or_role
        #       byte    flags
        #       TString account_icon
        #       TString clan_tag_or_symbol
        #       TString extra_player_data
        #
        # ReadWString and ReadTString both consume NUL-terminated UTF-8 bytes.
        snapshot = bytearray()
        snapshot += cstr(channel)
        snapshot += struct.pack("<I", channel_id)
        snapshot += struct.pack("<B", 0)       # channel flags
        snapshot += cstr("")                  # empty topic/message
        snapshot += struct.pack("<I", 0)      # no auxiliary entries
        snapshot += struct.pack("<I", len(members))

        for member in members:
            snapshot += cstr(member.nickname)
            snapshot += struct.pack("<I", member.account_id)
            snapshot += struct.pack("<B", 0)  # normal status/role
            snapshot += struct.pack("<B", 0)  # no member flags
            snapshot += cstr("")              # account icon
            snapshot += cstr("")              # clan tag/symbol
            snapshot += cstr("")              # extra player data

        self.send_packet(HON_SC_CHANGED_CHANNEL, bytes(snapshot))

        # Existing members need the incremental join event so their roster updates.
        joined = bytearray()
        joined += struct.pack("<I", channel_id)
        joined += cstr(self.state.nickname)
        joined += struct.pack("<I", self.state.account_id)
        joined += struct.pack("<B", 0)
        joined += struct.pack("<B", 0)
        joined += cstr("")
        joined += cstr("")
        joined += cstr("")
        for member in existing:
            try:
                member.handler.send_packet(HON_SC_JOINED_CHANNEL, bytes(joined))
            except OSError:
                pass

    def channel_message(self, payload: bytes):
        # Documented client form: s I (message, channel id)
        try:
            message, o = read_cstr(payload, 0)
            channel_id = struct.unpack_from("<I", payload, o)[0] if len(payload) >= o + 4 else self.state.chat_id
        except Exception as exc:
            log(f"CHANNEL MSG PARSE ERROR | {self.peer} | {exc}")
            return

        log(f"CHANNEL MSG | {self.state.nickname}@{self.state.channel} | {message!r}")
        # Documented server form: I I s (account id, channel id, message)
        response = struct.pack("<II", self.state.account_id, channel_id) + cstr(message)
        for member in WORLD.channel_members(self.state.channel or ""):
            try:
                member.handler.send_packet(HON_SC_CHANNEL_MSG, response)
            except OSError:
                pass

    def process(self, command: int, payload: bytes, raw: bytes):
        save_capture(self.peer, "client_to_server", raw,
                     command=f"0x{command:04X}", payload_length=len(payload))
        log(f"RX | {self.peer} | cmd=0x{command:04X} payload={len(payload)}")

        if command == HON_CS_AUTH_INFO:
            self.auth(payload)
        elif command == HON_CS_PONG:
            log(f"PONG | {self.peer}")
        elif command == 0x00B9:
            # Post-auth presence request. Protocol 47 then expects a server
            # status update packet 0x66 containing:
            #   byte status
            #   NUL-terminated UTF-8 string (ReadWString converts it to wide)
            #
            # status 0 = normal online
            status_payload = b"\x00\x00"
            self.send_packet(HON_SC_STATUS_UPDATE, status_payload)
            log(f"STATUS ONLINE | {self.peer} | sent cmd=0x0066 status=0")
        elif not self.authed:
            log(f"IGNORED PRE-AUTH | {self.peer} | cmd=0x{command:04X}")
        elif command == HON_CS_JOIN_CHANNEL:
            self.join_channel(payload)
        elif command == HON_CS_CHANNEL_MSG:
            self.channel_message(payload)
        elif command == HON_CS_LEAVE_CHANNEL:
            log(f"LEAVE CHANNEL | {self.peer}")
        else:
            log(f"UNKNOWN | {self.peer} | cmd=0x{command:04X} hex={payload.hex()}")

    def handle(self):
        while not self.stop.is_set():
            try:
                chunk = self.request.recv(65536)
            except socket.timeout:
                continue
            except OSError as exc:
                log(f"SOCKET ERROR | {self.peer} | {exc}")
                return
            if not chunk:
                return

            self.buffer += chunk
            save_capture(self.peer, "tcp_chunk", chunk, buffered_after_chunk=len(self.buffer))
            log(f"TCP RX | {self.peer} | chunk={len(chunk)} buffer={len(self.buffer)}")

            while True:
                try:
                    packet = extract_packet(self.buffer)
                except ValueError as exc:
                    log(f"FRAMING ERROR | {self.peer} | {exc} | hex={self.buffer[:64].hex()}")
                    return
                if packet is None:
                    break
                total, command, payload, raw = packet
                self.buffer = self.buffer[total:]
                self.process(command, payload, raw)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="0.0.0.0 permits LAN clients; default: %(default)s")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", help="Path to the v24 master server thorgor_accounts.db")
    args = parser.parse_args()

    global ACCOUNT_DB_PATH
    try:
        ACCOUNT_DB_PATH = discover_account_db(args.db)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Account database error: {exc}")
        return 2

    try:
        server = ThreadedTCPServer((args.host, args.port), ChatConnection)
    except OSError as exc:
        print(f"Could not bind {args.host}:{args.port}: {exc}")
        print(f"Check: netstat -ano | findstr :{args.port}")
        return 1

    print("=" * 88)
    print(APP_NAME)
    print(f"Listening: TCP {args.host}:{args.port}")
    print(f"Account database: {ACCOUNT_DB_PATH}")
    print("Observed client: HoN 3.2.7.1, protocol 47")
    print("Expected auth accepted bytes: 02 00 00 1c")
    print(f"Log: {LOG_PATH}")
    print("=" * 88)

    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
