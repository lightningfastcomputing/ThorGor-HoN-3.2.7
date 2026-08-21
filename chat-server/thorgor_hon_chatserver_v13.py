#!/usr/bin/env python3
"""
ThorGor HoN LAN Chat Server v11
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
import sys
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

APP_NAME = "ThorGor HoN LAN Chat Server v13 - 3.2.7 Registration Probe"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 11031
DEFAULT_NICK = "Guest"
ACCOUNT_DB_PATH: Path | None = None

# 16-bit special commands
HON_CS_AUTH_INFO = 0x0C00
# ProjectKONGOR / data-mined game-server and manager control commands.
NET_CHAT_GS_CONNECT = 0x0500
NET_CHAT_GS_STATUS = 0x0502
NET_CHAT_GS_ACCEPT = 0x1500
NET_CHAT_SM_CONNECT = 0x1600
NET_CHAT_SM_STATUS = 0x1602
NET_CHAT_SM_ACCEPT = 0x1700
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

BASE_DIR = ((Path(sys.executable).resolve().parent / "chat-server")
            if getattr(sys, "frozen", False) else Path(__file__).resolve().parent)
LOG_PATH = BASE_DIR / "thorgor_chat_v13.log"
CAPTURE_DIR = BASE_DIR / "thorgor_chat_v13_captures"
CAPTURE_DIR.mkdir(exist_ok=True)
HOST_CAPTURE_DIR = BASE_DIR / "thorgor_chat_v13_host_captures"
HOST_CAPTURE_DIR.mkdir(exist_ok=True)
HOST_LOG_PATH = BASE_DIR / "thorgor_chat_v13_host.log"
LOG_LOCK = threading.Lock()
V31_STATE_PATH = BASE_DIR.parent / "work" / "v31_registration_state.json"
V31_STATE_LOCK = threading.RLock()

def v31_read_state():
    with V31_STATE_LOCK:
        try:
            return json.loads(V31_STATE_PATH.read_text(encoding="utf-8-sig"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

def v31_update_state(**updates):
    with V31_STATE_LOCK:
        state = v31_read_state()
        state.update(updates)
        state["chat_updated_at"] = datetime.now().isoformat(timespec="seconds")
        V31_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = V31_STATE_PATH.with_suffix(".chat.tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True)+"\n", encoding="utf-8")
        tmp.replace(V31_STATE_PATH)
        return state


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]


def log(msg: str) -> None:
    line = f"{stamp()} | {msg}"
    with LOG_LOCK:
        print(line, flush=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def host_log(msg: str) -> None:
    line = f"{stamp()} | HOST_CONTROL | {msg}"
    with LOG_LOCK:
        print(line, flush=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        with HOST_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def is_host_username(username: str) -> bool:
    """Identify manager-created slave identities such as thorgorhost:1."""
    base, sep, suffix = username.rpartition(":")
    return bool(sep and base and suffix.isdigit())


def cstr(text: str) -> bytes:
    return text.encode("utf-8", errors="replace") + b"\x00"


def read_cstr(data: bytes, offset: int) -> tuple[str, int]:
    end = data.find(b"\x00", offset)
    if end < 0:
        raise ValueError("unterminated string")
    return data[offset:end].decode("utf-8", errors="replace"), end + 1


def save_capture(peer: str, direction: str, data: bytes, *, directory: Path | None = None, **extra) -> None:
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
    target_dir = directory or CAPTURE_DIR
    target_dir.mkdir(exist_ok=True)
    (target_dir / name).write_text(json.dumps(record, indent=2), encoding="utf-8")




def diagnostic_chat_context(state: "ClientState", command: int, payload: bytes) -> dict:
    """Build account-correlated context for post-auth commands under investigation.

    Diagnostic only: this function never changes protocol behavior.
    """
    shared = v31_read_state()
    decoded = None
    if command == 0x000F:
        try:
            decoded, _ = read_cstr(payload, 0)
        except Exception:
            decoded = payload.decode("utf-8", errors="replace").rstrip("\x00")
    return {
        "account": state.username,
        "account_id": state.account_id,
        "nickname": state.nickname,
        "channel": state.channel,
        "chat_id": state.chat_id,
        "command": f"0x{command:04X}",
        "payload_hex": payload.hex(),
        "decoded_endpoint": decoded,
        "lifecycle": shared.get("lifecycle"),
        "match_id": shared.get("match_id"),
        "match_name": shared.get("match_name"),
        "match_host_account_id": shared.get("match_host_account_id"),
        "match_host_nickname": shared.get("match_host_nickname"),
        "server_ip": shared.get("server_ip"),
        "server_port": shared.get("server_port"),
        "server_status": shared.get("server_status"),
    }

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
    username: str = ""
    nickname: str = DEFAULT_NICK
    channel: Optional[str] = None
    chat_id: int = 0
    is_host: bool = False


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
        self.control_role = None
        self.request.settimeout(1.0)
        log(f"CONNECT | {self.peer}")

    def finish(self):
        self.stop.set()
        if self.control_role == "game_server":
            v31_update_state(chat_server_connected=False, idle_confirmed=False, lifecycle="chat_disconnected")
        elif self.control_role == "manager":
            v31_update_state(manager_chat_connected=False)
        WORLD.unregister(self.state)
        if self.state.is_host:
            host_log(f"DISCONNECT account={self.state.username!r} peer={self.peer}")
        log(f"DISCONNECT | {self.peer}")

    def send_packet(self, command: int, payload: bytes = b""):
        frame = encode_packet(command, payload)
        with self.send_lock:
            self.request.sendall(frame)
        save_capture(self.peer, "server_to_client", frame,
                     command=f"0x{command:04X}", payload_length=len(payload))
        log(f"TX | {self.peer} | cmd=0x{command:04X} payload={len(payload)} total={len(frame)}")
        if self.state.is_host:
            save_capture(
                self.peer,
                "host_server_to_peer",
                frame,
                directory=HOST_CAPTURE_DIR,
                account=self.state.username,
                command=f"0x{command:04X}",
                payload_length=len(payload),
            )
            host_log(
                f"TX_RAW account={self.state.username!r} peer={self.peer} cmd=0x{command:04X} "
                f"payload={len(payload)} total={len(frame)} frame_hex={frame.hex()}"
            )

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

    def auth(self, payload: bytes, raw: bytes):
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
        self.state.username = account.username
        self.state.nickname = account.nickname
        self.state.is_host = is_host_username(account.username)
        self.authed = True
        WORLD.register(self.state)

        if self.state.is_host:
            save_capture(
                self.peer,
                "host_peer_to_server",
                raw,
                directory=HOST_CAPTURE_DIR,
                account=self.state.username,
                command=f"0x{HON_CS_AUTH_INFO:04X}",
                payload_length=len(payload),
                parsed_auth=info,
            )
            host_log(
                f"IDENTIFIED account={self.state.username!r} peer={self.peer} protocol={info['protocol']} "
                f"AUTH_RAW frame_hex={raw.hex()}"
            )

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

    def game_server_connect(self, payload: bytes):
        try:
            off=0
            server_id=struct.unpack_from("<I",payload,off)[0]; off+=4
            session,off=read_cstr(payload,off)
            protocol=struct.unpack_from("<I",payload,off)[0]
        except Exception as exc:
            log(f"GS CONNECT PARSE ERROR | {self.peer} | {exc} | {payload.hex()}")
            return
        state=v31_read_state()
        if int(state.get("server_id",-1)) != server_id or state.get("server_session") != session:
            log(f"GS CONNECT REJECT | {self.peer} server_id={server_id} protocol={protocol}")
            return
        self.authed=True; self.control_role="game_server"
        v31_update_state(chat_server_connected=True, chat_server_protocol=protocol)
        self.send_packet(NET_CHAT_GS_ACCEPT)
        log(f"GS CONNECT ACCEPT | {self.peer} server_id={server_id} protocol={protocol}")

    def manager_connect(self, payload: bytes):
        try:
            off=0
            manager_id=struct.unpack_from("<I",payload,off)[0]; off+=4
            session,off=read_cstr(payload,off)
            protocol=struct.unpack_from("<I",payload,off)[0]
        except Exception as exc:
            log(f"SM CONNECT PARSE ERROR | {self.peer} | {exc} | {payload.hex()}")
            return
        state=v31_read_state()
        if int(state.get("manager_id",-1)) != manager_id or state.get("manager_session") != session:
            log(f"SM CONNECT REJECT | {self.peer} manager_id={manager_id} protocol={protocol}")
            return
        self.authed=True; self.control_role="manager"
        v31_update_state(manager_chat_connected=True, manager_chat_protocol=protocol)
        self.send_packet(NET_CHAT_SM_ACCEPT)
        log(f"SM CONNECT ACCEPT | {self.peer} manager_id={manager_id} protocol={protocol}")

    def game_server_status(self, payload: bytes):
        """Decode both the older and later HoN GS STATUS layouts.

        Common prefix:
          u32 server_id, cstr address, i16 port, cstr location, cstr name

        Older builds then place status immediately. Later builds (the layout
        Project KONGOR data-mined) insert u32 slave_id + u32 match_id first.
        v13 accepts either and logs the raw tail so 3.2.7 tells us which it uses.
        """
        try:
            off = 0
            server_id = struct.unpack_from("<I", payload, off)[0]; off += 4
            address, off = read_cstr(payload, off)
            port = struct.unpack_from("<H", payload, off)[0]; off += 2
            location, off = read_cstr(payload, off)
            name, off = read_cstr(payload, off)
            tail = payload[off:]
            if not tail:
                raise ValueError("empty status tail")

            old_status = tail[0] if tail[0] <= 6 else None
            slave_id = None
            match_id = None
            new_status = None
            if len(tail) >= 9:
                cand_slave = struct.unpack_from("<I", tail, 0)[0]
                cand_match = struct.unpack_from("<I", tail, 4)[0]
                cand_status = tail[8]
                if cand_status <= 6 and cand_slave < 4096:
                    slave_id, match_id, new_status = cand_slave, cand_match, cand_status

            if new_status is not None:
                layout = "kongor/slave+match"
                status = new_status
            elif old_status is not None:
                layout = "legacy/direct-status"
                status = old_status
            else:
                raise ValueError(f"no plausible status byte in tail {tail[:24].hex()}")
        except Exception as exc:
            log(f"GS STATUS PARSE ERROR | {self.peer} | {exc} | {payload[:160].hex()}")
            v31_update_state(last_status_parse_error=str(exc), last_status_payload_hex=payload.hex())
            return

        names = {0:"sleeping", 1:"idle", 2:"loading", 3:"active", 4:"crashed", 5:"killed", 6:"unknown"}
        status_name = names.get(status, f"status_{status}")
        v31_update_state(
            server_id=server_id, server_ip=address, server_port=port, server_location=location,
            server_name=name, slave_id=slave_id, match_id=match_id, server_status=status,
            lifecycle=status_name, idle_confirmed=(status==1), sleeping_confirmed=(status==0),
            available_confirmed=(status in (0,1)), chat_server_connected=True,
            status_layout=layout, last_status_payload_hex=payload.hex()
        )
        log(f"GS STATUS | {self.peer} id={server_id} slave={slave_id} {address}:{port} "
            f"status={status_name} match={match_id} layout={layout} tail={tail[:32].hex()}")

    def process(self, command: int, payload: bytes, raw: bytes):
        save_capture(self.peer, "client_to_server", raw,
                     command=f"0x{command:04X}", payload_length=len(payload))
        log(f"RX | {self.peer} | cmd=0x{command:04X} payload={len(payload)}")

        if command != HON_CS_AUTH_INFO and self.state.is_host:
            save_capture(
                self.peer,
                "host_peer_to_server",
                raw,
                directory=HOST_CAPTURE_DIR,
                account=self.state.username,
                command=f"0x{command:04X}",
                payload_length=len(payload),
            )
            host_log(
                f"RX_RAW account={self.state.username!r} peer={self.peer} cmd=0x{command:04X} "
                f"payload={len(payload)} total={len(raw)} frame_hex={raw.hex()} payload_hex={payload.hex()}"
            )

        if command == NET_CHAT_GS_CONNECT:
            self.game_server_connect(payload)
        elif command == NET_CHAT_SM_CONNECT:
            self.manager_connect(payload)
        elif command == NET_CHAT_GS_STATUS and self.control_role == "game_server":
            self.game_server_status(payload)
        elif command == NET_CHAT_SM_STATUS and self.control_role == "manager":
            log(f"SM STATUS | {self.peer} payload={payload.hex()}")
        elif command == HON_CS_AUTH_INFO:
            self.auth(payload, raw)
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
            if self.state.is_host:
                host_log(
                    f"COMPAT account={self.state.username!r} cmd=0x00B9 currently handled with client-style "
                    "0x0066 online response; preserved from v8 for observation"
                )
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
        elif command in {0x0D07, 0x000F, 0x0011}:
            # Diagnostic-only observation of the recurring post-auth/game-transition
            # commands.  Do not send a guessed reply until we know their semantics.
            context = diagnostic_chat_context(self.state, command, payload)
            log(
                "TRANSITION_PROBE "
                f"account={self.state.username!r} account_id={self.state.account_id} "
                f"peer={self.peer} cmd=0x{command:04X} "
                f"channel={self.state.channel!r} lifecycle={context['lifecycle']!r} "
                f"match_id={context['match_id']!r} endpoint={context['decoded_endpoint']!r} "
                f"payload_hex={payload.hex()}"
            )
            save_capture(
                self.peer,
                "transition_probe",
                raw,
                **context,
            )
        else:
            if self.state.is_host:
                host_log(
                    f"UNKNOWN account={self.state.username!r} peer={self.peer} cmd=0x{command:04X} "
                    f"payload_hex={payload.hex()}"
                )
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
            if self.state.is_host:
                save_capture(
                    self.peer,
                    "host_tcp_chunk",
                    chunk,
                    directory=HOST_CAPTURE_DIR,
                    account=self.state.username,
                    buffered_after_chunk=len(self.buffer),
                )
                host_log(
                    f"TCP_CHUNK account={self.state.username!r} peer={self.peer} bytes={len(chunk)} "
                    f"buffer={len(self.buffer)} chunk_hex={chunk.hex()}"
                )

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
    print(f"Host/slave raw log: {HOST_LOG_PATH}")
    print(f"Host/slave raw captures: {HOST_CAPTURE_DIR}")
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
    log(f"PROCESS_START | pid={os.getpid()} argv={sys.argv!r}")
    raise SystemExit(main())
