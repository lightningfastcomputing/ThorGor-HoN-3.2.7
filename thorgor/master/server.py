#!/usr/bin/env python3
"""
ThorGor HoN 3.2.7 LAN master/auth service.

Implements the legacy HoN two-stage SRP-6a login observed in k2.dll:

    POST f=pre_auth
         login=<account>
         A=<2048-bit client public value>

    response: salt, B, salt2

    POST f=srpAuth
         login=<account>
         proof=<client M1>
         OSType, MajorVersion, MinorVersion, MicroVersion

    response: proof=<server HAMK/M2> plus a minimal local account payload

This is intended only for an isolated/local HoN sandbox.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, urlparse

from thorgor.paths import ROOT
from thorgor.master.game_authorization import GAME_AUTHORIZATION
from thorgor.master.products import CATALOG as PRODUCT_CATALOG
from thorgor.master.accounts import (
    Account as PersistentAccount,
    AccountStore as PersistentAccountStore,
    GameAuthorization as PersistentGameAuthorization,
)
from thorgor.matchmaking.endpoint import DedicatedServerAllocator, MatchmakingEndpoint
from thorgor.master import auth as auth_primitives
from thorgor.master.sessions import Runtime as SessionRuntime, Session as AuthenticationSession
from thorgor.master.server_list import ServerListService

APP_NAME = "ThorGor HoN 3.2.7 LAN Master Service"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 80

BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT
LOG_PATH = BASE_DIR / "thorgor_srp_v39.log"
CAPTURE_DIR = BASE_DIR / "thorgor_srp_v39_captures"
CAPTURE_DIR.mkdir(exist_ok=True)
SERVER_CAPTURE_DIR = BASE_DIR / "thorgor_server_v39_captures"
SERVER_CAPTURE_DIR.mkdir(exist_ok=True)
SERVER_LOG_PATH = BASE_DIR / "thorgor_server_v39.log"

# Create positive startup evidence before binding port 80. This makes a stale/old
# master impossible to mistake for v27 during collection.
def _write_startup_marker() -> None:
    marker = f"{datetime.now().isoformat(timespec='milliseconds')} | PROCESS_START | pid={os.getpid()} argv={sys.argv!r}\n"
    for path in (LOG_PATH, SERVER_LOG_PATH):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(marker)


# k2.dll custom SRP group.
S2_N_HEX = (
    "DA950C6C97918CAE89E4F5ECB32461032A217D740064BC12FC0723CD204BD02A7AE29B53F3310C13BA998B7910F8B6A14112CBC67BDD2427E"
    "DF494CB8BCA68510C0AAEE5346BD320845981546873069B337C073B9A9369D500873D647D261CCED571826E54C6089E7D5085DC2AF01FD861"
    "AE44C8E64BCA3EA4DCE942C5F5B89E5496C2741A9E7E9F509C261D104D11DD4494577038B33016E28D118AE4FD2E85D9C3557A2346FAECED3"
    "EDBE0F4D694411686BA6E65FEE43A772DC84D394ADAE5A14AF33817351D29DE074740AA263187AB18E3A25665EACAA8267C16CDE064B1D5AF"
    "0588893C89C1556D6AEF644A3BA6BA3F7DEC2F3D6FDC30AE43FBD6D144BB"
)
N = int(S2_N_HEX, 16)
G = 2
WIDTH = 0x100  # 256 bytes / 2048 bits
HASH = hashlib.sha256

MAGIC1 = "[!~esTo0}"
MAGIC2 = "taquzaph_?98phab&junaj=z=kuChusu"
CHAT_SERVER_AUTHENTICATION_SALT = "8roespiemlasToUmiuglEhOaMiaSWlesplUcOAniupr2esPOeBRiudOEphiutOuJ"


class Config:
    salt2 = "p^^^&bjRlXi4B=A1y.@Vz)"
    password_chain = "pre-md5"
    session_ttl = 300
    database_path = BASE_DIR / "thorgor_accounts.db"
    chat_host = "127.0.0.1"
    server_list_ip = ""
    server_list_port = 11236
    server_list_class = 1
    match_server_id = 1
    match_server_ip = "127.0.0.1"
    match_server_port = 11235
    match_server_location = "USE"


CONFIG = Config()
MATCHMAKING: MatchmakingEndpoint | None = None

# The private ThorGor service has no cash shop or per-account catalog.  HoN's
# non-host client still runs the legacy ownership gate while it constructs the
# hero picker, so advertise the retail all-heroes product on both auth paths.
LAN_ACCOUNT_UPGRADES = ("h.AllHeroes.Hero",)
PRODUCT_CATEGORIES = (
    "Alt Avatar",
    "Taunt",
    "Misc",
    "Alt Announcement",
    "Couriers",
    "Hero",
    "Ward",
    "EAP",
    "Mastery",
)

# v31 readiness state. KONGOR's newer implementation only exposes a server for
# CREATE when it is authenticated, has reported Idle, and is actually reachable.
# For 3.2.7 we preserve that invariant instead of advertising a synthetic row
# merely because a process/UDP shim exists.
V31_STATE_PATH = BASE_DIR / "work" / "v31_registration_state.json"
V31_CONTROL_FLAG = BASE_DIR / "work" / "v31_manager_control.connected"
V31_STATE_LOCK = threading.RLock()

def v31_read_state() -> dict[str, Any]:
    with V31_STATE_LOCK:
        try:
            return json.loads(V31_STATE_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {"registered": False, "idle_confirmed": False, "lifecycle": "offline"}

def v31_update_state(**updates: Any) -> dict[str, Any]:
    with V31_STATE_LOCK:
        state = v31_read_state()
        state.update(updates)
        state["updated_at"] = datetime.now().isoformat(timespec="seconds")
        V31_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = V31_STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(V31_STATE_PATH)
        return state

def v39_vessel_ready() -> bool:
    """Return True only when a real server control path is currently alive.

    v31 gated CREATE rows on server_requester+chat registration. 3.2.7.1 has
    now given us a stronger live signal: the original slave's real 0x40
    association to the original manager. v39 accepts either proven path, but
    it never advertises a row merely because UDP 11235 happens to be bound.
    """
    state = v31_read_state()
    status = state.get("server_status")
    manager_ready = bool(
        state.get("manager_control_connected")
        and state.get("manager_associated")
    )
    chat_ready = bool(
        state.get("registered")
        and state.get("chat_server_connected")
    )
    return bool(status in (0, 1) and (manager_ready or chat_ready))


@dataclass(frozen=True)
class Account:
    account_id: int
    username: str
    password: str
    nickname: str
    enabled: bool


@dataclass(frozen=True)
class GameAuthorization:
    account: Account
    cookie: str
    game_cookie: str


class AccountStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.RLock()
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock, self.connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    transformed_password TEXT,
                    password TEXT,
                    nickname TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS game_authorizations (
                    account_id INTEGER PRIMARY KEY,
                    cookie TEXT NOT NULL UNIQUE,
                    game_cookie TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS matches (
                    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER NOT NULL,
                    server_session TEXT NOT NULL,
                    map TEXT NOT NULL DEFAULT '',
                    version TEXT NOT NULL DEFAULT '',
                    match_name TEXT NOT NULL DEFAULT '',
                    casual TEXT NOT NULL DEFAULT '',
                    match_mode TEXT NOT NULL DEFAULT '',
                    accounts TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # v20 stored only a derived credential. v22 intentionally stores the local
            # sandbox password so login executes the exact known-working v19 path.
            columns = {row[1] for row in db.execute("PRAGMA table_info(accounts)").fetchall()}
            if "password" not in columns:
                db.execute("ALTER TABLE accounts ADD COLUMN password TEXT")
            db.commit()

    def add_or_update(self, username: str, password: str, nickname: str | None = None) -> Account:
        username = username.strip()
        if not username:
            raise ValueError("Username cannot be empty")
        if not password:
            raise ValueError("Password cannot be empty")
        nickname = (nickname or username).strip() or username
        with self.lock, self.connect() as db:
            db.execute(
                """
                INSERT INTO accounts (username, transformed_password, password, nickname, enabled)
                VALUES (?, NULL, ?, ?, 1)
                ON CONFLICT(username) DO UPDATE SET
                    transformed_password = NULL,
                    password = excluded.password,
                    nickname = excluded.nickname,
                    enabled = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (username, password, nickname),
            )
            db.commit()
        account = self.get(username, include_disabled=True)
        if account is None:
            raise RuntimeError("Account was not saved")
        return account

    def get(self, username: str, *, include_disabled: bool = False) -> Account | None:
        query = "SELECT account_id, username, password, nickname, enabled FROM accounts WHERE username = ?"
        values: list[Any] = [username]
        if not include_disabled:
            query += " AND enabled = 1"
        with self.lock, self.connect() as db:
            row = db.execute(query, values).fetchone()
        if row is None:
            return None
        return Account(
            account_id=int(row["account_id"]),
            username=str(row["username"]),
            password=str(row["password"] or ""),
            nickname=str(row["nickname"]),
            enabled=bool(row["enabled"]),
        )

    def register_game_authorization(self, account_id: int) -> GameAuthorization:
        cookie = f"THORGOR_LOCAL_COOKIE_{account_id:08d}"
        game_cookie = secrets.token_hex(16)
        with self.lock, self.connect() as db:
            row = db.execute(
                "SELECT account_id, username, password, nickname, enabled FROM accounts WHERE account_id = ? AND enabled = 1",
                (account_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Cannot authorize an unknown or disabled account")
            db.execute(
                """
                INSERT INTO game_authorizations (account_id, cookie, game_cookie)
                VALUES (?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    cookie = excluded.cookie,
                    game_cookie = excluded.game_cookie,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (account_id, cookie, game_cookie),
            )
            db.commit()
        account = Account(
            account_id=int(row["account_id"]),
            username=str(row["username"]),
            password=str(row["password"] or ""),
            nickname=str(row["nickname"]),
            enabled=bool(row["enabled"]),
        )
        return GameAuthorization(account=account, cookie=cookie, game_cookie=game_cookie)

    def get_game_authorization(self, cookie: str) -> GameAuthorization | None:
        with self.lock, self.connect() as db:
            row = db.execute(
                """
                SELECT a.account_id, a.username, a.password, a.nickname, a.enabled,
                       g.cookie, g.game_cookie
                FROM game_authorizations AS g
                JOIN accounts AS a ON a.account_id = g.account_id
                WHERE g.cookie = ? AND a.enabled = 1
                """,
                (cookie,),
            ).fetchone()
        if row is None:
            return None
        account = Account(
            account_id=int(row["account_id"]),
            username=str(row["username"]),
            password=str(row["password"] or ""),
            nickname=str(row["nickname"]),
            enabled=bool(row["enabled"]),
        )
        return GameAuthorization(
            account=account,
            cookie=str(row["cookie"]),
            game_cookie=str(row["game_cookie"]),
        )

    def create_match(self, server_id: int, server_session: str, params: dict[str, list[str]]) -> int:
        def parameter(name: str) -> str:
            return params.get(name, [""])[0]

        with self.lock, self.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO matches (
                    server_id, server_session, map, version, match_name,
                    casual, match_mode, accounts
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    server_id,
                    server_session,
                    parameter("map"),
                    parameter("version"),
                    parameter("mname"),
                    parameter("casual"),
                    parameter("match_mode"),
                    parameter("accounts"),
                ),
            )
            db.commit()
            match_id = int(cursor.lastrowid)
        if match_id <= 0:
            raise RuntimeError("SQLite did not allocate a positive match ID")
        return match_id

    def list_accounts(self) -> list[Account]:
        with self.lock, self.connect() as db:
            rows = db.execute(
                "SELECT account_id, username, password, nickname, enabled FROM accounts ORDER BY account_id"
            ).fetchall()
        return [
            Account(
                account_id=int(row["account_id"]),
                username=str(row["username"]),
                password=str(row["password"] or ""),
                nickname=str(row["nickname"]),
                enabled=bool(row["enabled"]),
            )
            for row in rows
        ]

    def set_enabled(self, username: str, enabled: bool) -> bool:
        with self.lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE accounts SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
                (1 if enabled else 0, username),
            )
            db.commit()
            return cursor.rowcount > 0

    def delete(self, username: str) -> bool:
        with self.lock, self.connect() as db:
            cursor = db.execute("DELETE FROM accounts WHERE username = ?", (username,))
            db.commit()
            return cursor.rowcount > 0

    def count(self) -> int:
        with self.lock, self.connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0])


# Compatibility names remain importable from this module while production
# ownership lives in thorgor.master.accounts.
Account = PersistentAccount
GameAuthorization = PersistentGameAuthorization
AccountStore = PersistentAccountStore
ACCOUNTS: PersistentAccountStore | None = None


def php_serialize(value: Any) -> bytes:
    if value is None:
        return b"N;"
    if value is True:
        return b"b:1;"
    if value is False:
        return b"b:0;"
    if isinstance(value, int):
        return f"i:{value};".encode("ascii")
    if isinstance(value, float):
        return f"d:{value!r};".encode("ascii")
    if isinstance(value, bytes):
        return b's:%d:"' % len(value) + value + b'";'
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return b's:%d:"' % len(raw) + raw + b'";'
    if isinstance(value, (list, tuple)):
        chunks: list[bytes] = []
        for index, item in enumerate(value):
            chunks.extend((php_serialize(index), php_serialize(item)))
        return b"a:%d:{" % len(value) + b"".join(chunks) + b"}"
    if isinstance(value, dict):
        chunks: list[bytes] = []
        for key, item in value.items():
            chunks.extend((php_serialize(key), php_serialize(item)))
        return b"a:%d:{" % len(value) + b"".join(chunks) + b"}"
    return php_serialize(str(value))


def int_bytes(value: int) -> bytes:
    if value == 0:
        return b"\x00"
    return value.to_bytes((value.bit_length() + 7) // 8, "big")


def pad_num(value: int) -> bytes:
    return value.to_bytes(WIDTH, "big")


def H(*parts: bytes) -> bytes:
    digest = HASH()
    for part in parts:
        digest.update(part)
    return digest.digest()


def xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def encoded_num(value: int, *, padded: bool) -> bytes:
    return pad_num(value) if padded else int_bytes(value)


def hon_password(password: str, salt2: str, chain: str) -> str:
    """
    k2.dll performs:
        MD5(<credential material> + salt2 + MAGIC1).hexdigest()
        SHA256(previous_hex + MAGIC2).hexdigest()

    The default 'direct' mode treats the entered password as that credential
    material. 'pre-md5' remains available because the hidden input to the first
    recovered concatenation still needs one controlled validation.
    """
    material = password
    if chain == "pre-md5":
        material = hashlib.md5(password.encode("utf-8")).hexdigest()

    stage1 = hashlib.md5(
        (material + salt2 + MAGIC1).encode("utf-8")
    ).hexdigest()
    return hashlib.sha256((stage1 + MAGIC2).encode("utf-8")).hexdigest()


# Authentication math is service-owned. Keep these names as the compatibility
# surface consumed by existing tests and older tools.
S2_N_HEX = auth_primitives.S2_N_HEX
N = auth_primitives.N
G = auth_primitives.G
WIDTH = auth_primitives.WIDTH
H = auth_primitives.H
xor_bytes = auth_primitives.xor_bytes
encoded_num = auth_primitives.encoded_num
int_bytes = auth_primitives.int_bytes
pad_num = auth_primitives.pad_num
hon_password = auth_primitives.hon_password
CHAT_SERVER_AUTHENTICATION_SALT = auth_primitives.CHAT_SERVER_AUTHENTICATION_SALT


@dataclass
class Session:
    account_id: int
    username: str
    nickname: str
    A: int
    salt: int
    salt2: str
    transformed_password: str
    b: int
    B: int
    v: int
    k: int
    u: int
    S: int
    K: bytes
    expected_M1: bytes
    M2: bytes
    created_at: float
    client_ip: str


class Runtime:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.sessions: dict[tuple[str, str], Session] = {}

    def cleanup(self) -> None:
        cutoff = time.time() - CONFIG.session_ttl
        stale = [key for key, value in self.sessions.items() if value.created_at < cutoff]
        for key in stale:
            self.sessions.pop(key, None)

    def store(self, session: Session) -> None:
        with self.lock:
            self.cleanup()
            self.sessions[(session.client_ip, session.username)] = session

    def get(self, client_ip: str, username: str) -> Session | None:
        with self.lock:
            self.cleanup()
            return self.sessions.get((client_ip, username))

    def consume(self, client_ip: str, username: str) -> None:
        with self.lock:
            self.sessions.pop((client_ip, username), None)

    def status(self) -> dict[str, Any]:
        with self.lock:
            self.cleanup()
            return {
                "active_sessions": len(self.sessions),
                "sessions": [
                    {
                        "client_ip": session.client_ip,
                        "username": session.username,
                        "age_seconds": round(time.time() - session.created_at, 3),
                    }
                    for session in self.sessions.values()
                ],
            }


Session = AuthenticationSession
Runtime = SessionRuntime
RUNTIME = Runtime(lambda: CONFIG.session_ttl)


def log(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    line = f"{stamp} | {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def server_log(message: str) -> None:
    """Write a high-signal control-plane line to both the master and server logs."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    line = f"{stamp} | SERVER_CONTROL | {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    with SERVER_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


# These names are documented in later HoN server implementations and are only
# used as diagnostic labels here. v27 does not assume 3.2.7 uses identical
# payloads or semantics; the raw request is always preserved.
SERVER_REQUEST_HINTS = {
    "new_session": "candidate game-server session/auth registration",
    "replay_auth": "candidate manager/session registration",
    "start_game": "candidate match-id/start-game request",
    "host_lobby": "verified final Create Game publication",
    "host_release": "release an abandoned host reservation",
    "c_conn": "candidate game-server client authorization",
    "client_auth": "candidate game-server client authorization alias",
    "accept_key": "candidate hosting permission/account-key validation",
    "set_online": "candidate server online/status transition",
    "shutdown": "candidate server shutdown notification",
    "get_upgrades": "candidate server-side upgrade lookup",
}


def create_session(
    username: str,
    password: str,
    account_id: int,
    nickname: str,
    A_hex: str,
    client_ip: str,
) -> Session:
    """
    Server-side mirror of the recovered k2.dll client SRP calculations.

    Confirmed by FUN_150f4c30 / FUN_150f3850 / FUN_150f3a80:
      x = H(PAD_256(salt) || H(username || ":" || transformed_password))
      k = H(PAD_256(N) || PAD_256(g))
      u = H(PAD_256(A) || PAD_256(B))
      K = H(PAD_256(S))

    B is reduced modulo N before transmission so the legacy client receives
    exactly one 2048-bit group element.
    """
    A = int(A_hex, 16)
    if not 0 < A < N or A % N == 0:
        raise ValueError("Invalid SRP A")

    salt = secrets.randbits(32) | (1 << 31)
    b = secrets.randbits(256) | (1 << 255)
    # Exact v19 behavior: transform the selected account password, then hash
    # the exact login string supplied by the HoN client.
    transformed = hon_password(password, CONFIG.salt2, CONFIG.password_chain)

    inner = H(
        username.encode("utf-8"),
        b":",
        transformed.encode("utf-8"),
    )

    # FUN_150f4c30 passes ceil(bit_length(N)/8), i.e. 0x100, as the
    # requested salt width to FUN_150f3a80/FUN_150f3920.
    x = int.from_bytes(H(pad_num(salt), inner), "big")
    v = pow(G, x, N)

    # FUN_150f3850 hashes two zero-left-padded WIDTH-byte integers.
    k = int.from_bytes(H(pad_num(N), pad_num(G)), "big")
    B = (k * v + pow(G, b, N)) % N

    u = int.from_bytes(H(pad_num(A), pad_num(B)), "big")
    if u == 0:
        raise ValueError("Invalid SRP scrambling parameter")

    # Verifier-side equivalent of the client's
    # (B - k*g^x)^(a + u*x) mod N.
    S = pow((A * pow(v, u, N)) % N, b, N)

    # FUN_150f3a20 hashes a fixed-width, zero-left-padded BIGNUM.
    K = H(pad_num(S))

    # Current best reconstruction of FUN_150f3bd0.
    M1 = H(
        xor_bytes(H(pad_num(N)), H(pad_num(G))),
        H(username.encode("utf-8")),
        pad_num(salt),
        pad_num(A),
        pad_num(B),
        K,
    )

    # Current best reconstruction of FUN_150f3f60.
    M2 = H(pad_num(A), M1, K)

    return Session(
        account_id=account_id,
        username=username,
        nickname=nickname,
        A=A,
        salt=salt,
        salt2=CONFIG.salt2,
        transformed_password=transformed,
        b=b,
        B=B,
        v=v,
        k=k,
        u=u,
        S=S,
        K=K,
        expected_M1=M1,
        M2=M2,
        created_at=time.time(),
        client_ip=client_ip,
    )

def preauth_payload(session: Session) -> dict[Any, Any]:
    return {
        "salt": format(session.salt, "x"),
        "B": f"{session.B:0512x}",
        "salt2": session.salt2,
        "vested_threshold": 5,
        0: True,
    }


def success_payload(session: Session, cookie: str | None = None) -> dict[Any, Any]:
    """
    Minimal typed account payload reconstructed from FUN_15317110.

    The legacy parser expects numeric fields as PHP integers, not numeric
    strings. Earlier builds used strings for account_id/account_type/trial,
    which could make GetInteger() return -1 or corrupt later state.

    The hero-ownership collections are supplied for the private LAN catalog;
    unrelated optional collections are omitted so those branches skip cleanly.
    """
    payload: dict[Any, Any] = {
        "proof": session.M2.hex(),

        # Required account gate.
        "account_id": session.account_id,
        "auth": "Authorized",
        "account_type": 5,

        # Required identity/session strings.
        "nickname": session.nickname,
        "email": "",
        "ip": "127.0.0.1",
        "cookie": cookie or f"THORGOR_LOCAL_COOKIE_{session.account_id:08d}",
        "auth_hash": hashlib.sha1(f"THORGOR_LOCAL_AUTH:{session.account_id}:{session.username}".encode("utf-8")).hexdigest(),

        # Safe scalar defaults read directly by FUN_15317110.
        "show_purchase": False,
        "standing": 3,
        "vested_threshold": 5,
        "pass_exp": "",
        "chat_url": CONFIG.chat_host,
        "mute_expiration": 0,
        "leaverthreshold": 0.0,
        "minimum_ranked_level": 0.0,
        "is_subaccount": False,

        # Parsed by the client before it builds the local hero registry.
        "my_upgrades": list(LAN_ACCOUNT_UPGRADES),
        "selected_upgrades": [],

        0: True,
    }

    # FUN_15304E90 in the 3.2.7.1 client reads this optional collection.
    # Each entry supplies the UDP browser with an address to probe; "class"
    # is read as an integer while "ip" and "port" are read as strings.
    if CONFIG.server_list_ip:
        payload["server_list"] = [
            {
                "class": CONFIG.server_list_class,
                "ip": CONFIG.server_list_ip,
                "port": str(CONFIG.server_list_port),
            }
        ]

    return payload


def start_game_response(
    store: AccountStore,
    params: dict[str, list[str]],
    expected_server_session: str | None,
    existing_match_id: int = 0,
    existing_match_date: str = "",
) -> dict[str, Any]:
    server_session = params.get("session", [""])[0]
    if not server_session:
        raise ValueError("Missing game-server session")
    if expected_server_session and not hmac.compare_digest(server_session, expected_server_session):
        raise ValueError("Invalid game-server session")

    match_id = existing_match_id
    if match_id <= 0:
        match_id = store.create_match(CONFIG.match_server_id, server_session, params)
    return {
        "match_id": match_id,
        "match_date": existing_match_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_recommended": False,
        "soccer_hero_list": "",
        "free_hero_list": "",
        "early_access_hero_list": "",
        "disabled_hero_list": "",
    }


def client_auth_response(store: AccountStore, params: dict[str, list[str]]) -> dict[str, Any]:
    cookie = params.get("cookie", [""])[0]
    if not cookie:
        raise ValueError("Missing player cookie")
    authorization = store.get_game_authorization(cookie)
    if authorization is None:
        raise ValueError("Invalid player cookie")

    neutral_stats = {
        "level": 1,
        "level_exp": 0.0,
        "acc_pub_skill": 1500.0,
        "rnk_amm_team_rating": 1500.0,
        "cs_amm_team_rating": 1500.0,
        "acc_games_played": 0,
        "rnk_games_played": 0,
        "cs_games_played": 0,
        "mid_games_played": 0,
        "cam_games_played": 0,
        "acc_discos": 0,
        "rnk_discos": 0,
        "cs_discos": 0,
        "mid_discos": 0,
        "cam_discos": 0,
    }
    return {
        "cookie": authorization.cookie,
        "account_id": authorization.account.account_id,
        "nickname": authorization.account.nickname,
        "super_id": authorization.account.account_id,
        "account_type": 5,
        "level": 1,
        "clan_id": -1,
        "tag": "",
        "infos": [neutral_stats],
        "game_cookie": authorization.game_cookie,
        "my_upgrades": list(LAN_ACCOUNT_UPGRADES),
        "selected_upgrades": [],
    }




def diagnostic_request_identity(store: AccountStore | None, params: dict[str, list[str]]) -> dict[str, Any]:
    """Resolve a master request to an account when its cookie is available.

    Diagnostic only; failures intentionally return anonymous context rather than
    influencing request handling.
    """
    cookie = params.get("cookie", [""])[0]
    result: dict[str, Any] = {
        "account": None,
        "account_id": None,
        "nickname": None,
        "cookie_present": bool(cookie),
    }
    if store is None or not cookie:
        return result
    try:
        authorization = store.get_game_authorization(cookie)
    except Exception:
        return result
    if authorization is None:
        return result
    result.update(
        account=authorization.account.username,
        account_id=authorization.account.account_id,
        nickname=authorization.account.nickname,
    )
    return result

def get_products_response(store: AccountStore, params: dict[str, list[str]]) -> dict[str, Any]:
    """Return the legacy store-catalog envelope required by HoN 3.2.7.1.

    Base hero ownership is conveyed by ``h.AllHeroes.Hero`` in ``my_upgrades``;
    it is not represented by one product per hero in this response.  The client
    still requires every legacy product category to be present before it can
    finish constructing its local product and hero registries.
    """
    cookie = params.get("cookie", [""])[0]
    if not cookie:
        raise ValueError("Missing product-catalog cookie")
    authorization = store.get_game_authorization(cookie)
    if authorization is None:
        raise ValueError("Invalid product-catalog cookie")

    supplied_account_id = params.get("account_id", [""])[0]
    if supplied_account_id:
        try:
            account_id = int(supplied_account_id)
        except ValueError as error:
            raise ValueError("Invalid product-catalog account ID") from error
        if account_id != authorization.account.account_id:
            raise ValueError("Product-catalog account ID does not match cookie")

    products = {category: {} for category in PRODUCT_CATEGORIES}
    serialised = json.dumps(products, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(serialised.encode("utf-8")).digest()
    crc = int.from_bytes(digest[:4], "little", signed=True)
    return {"products": products, "crc": crc}


# HTTP routing consumes service-owned implementations. These aliases preserve
# the historical import API while removing state ownership from the handler.
client_auth_response = GAME_AUTHORIZATION.authorize
diagnostic_request_identity = GAME_AUTHORIZATION.identity
get_products_response = PRODUCT_CATALOG.response


def match_server_list_payload(cookie: str, game_type: str) -> dict[Any, Any]:
    """Build the legacy response for ``f=server_list``.

    Game type 90 contains idle vessels available to host a new public game.
    Game type 10 contains vessels that already own a live lobby.  A vessel
    must never appear in both lists at once.
    """
    account_key = str(uuid.uuid4())
    account_key_hash = hashlib.sha1(
        (account_key + cookie + CHAT_SERVER_AUTHENTICATION_SALT).encode("utf-8")
    ).hexdigest()

    servers: dict[int, dict[str, str]] = {}
    state = v31_read_state()
    ready = v39_vessel_ready()
    pending_host_key = str(state.get("pending_host_key") or "")
    try:
        reservation_age = time.time() - float(state.get("pending_host_reserved_at", 0.0))
    except (TypeError, ValueError):
        reservation_age = float("inf")
    reserved = bool(pending_host_key) and 0.0 <= reservation_age < 60.0
    if pending_host_key and not reserved:
        state = v31_update_state(
            pending_host_key="",
            pending_host_account_id=0,
            pending_host_nickname="",
            pending_host_reserved_at=0.0,
            lifecycle="idle" if not state.get("match_id") else state.get("lifecycle", "lobby"),
        )
    try:
        lobby_active = int(state.get("match_id", 0)) > 0
    except (TypeError, ValueError):
        lobby_active = False

    # CREATE-game rows must point at the browser shim, not directly at the
    # original slave. The shim answers the legacy 0xCA health probe and then
    # forwards real C0/C9 game traffic unchanged to UDP 11235.
    picker_ip = CONFIG.server_list_ip or CONFIG.match_server_ip
    picker_port = CONFIG.server_list_port
    if game_type == "90" and picker_ip and ready and not lobby_active and not reserved:
        servers[CONFIG.match_server_id] = {
            "server_id": str(CONFIG.match_server_id),
            "ip": picker_ip,
            "port": str(picker_port),
            "location": CONFIG.match_server_location,
            "c_state": "1",
        }
        server_log(
            f"PUBLIC_PICKER_ROW gametype=90 server_id={CONFIG.match_server_id} "
            f"advertised={picker_ip}:{picker_port} real_slave={CONFIG.match_server_ip}:{CONFIG.match_server_port} "
            f"status={state.get('server_status')} source={state.get('manager_status_source', state.get('status_layout', 'unknown'))}"
        )
    elif game_type == "90":
        server_log(
            "PUBLIC_PICKER_EMPTY gametype=90 "
            f"ready={ready} manager_connected={state.get('manager_control_connected')} "
            f"associated={state.get('manager_associated')} registered={state.get('registered')} "
            f"chat_connected={state.get('chat_server_connected')} status={state.get('server_status')} "
            f"reserved={reserved} lobby_active={lobby_active} match_id={state.get('match_id')}"
        )

    # Project KONGOR's join response uses the same endpoint fields as CREATE,
    # but the discriminator is named "class" instead of "c_state".  The
    # A JOIN row exists only after start_game allocated a positive match ID.
    if game_type == "10" and picker_ip and ready and lobby_active:
        servers[CONFIG.match_server_id] = {
            "server_id": str(CONFIG.match_server_id),
            "ip": picker_ip,
            "port": str(picker_port),
            "location": CONFIG.match_server_location,
            "class": "1",
        }
        server_log(
            f"PUBLIC_JOIN_ROW gametype=10 server_id={CONFIG.match_server_id} "
            f"advertised={picker_ip}:{picker_port} real_slave={CONFIG.match_server_ip}:{CONFIG.match_server_port} "
            f"match_id={state.get('match_id')} status={state.get('server_status')}"
        )
    elif game_type == "10":
        server_log(
            "PUBLIC_JOIN_EMPTY gametype=10 "
            f"ready={ready} registered={state.get('registered')} status={state.get('server_status')} "
            f"lobby_active={lobby_active} match_id={state.get('match_id')}"
        )

    response: dict[Any, Any] = {
        "server_list": servers,
        "vested_threshold": 5,
        0: True,
    }
    # The hosting permission token exists only on the CREATE contract.
    if game_type == "90":
        response["acc_key"] = account_key
        response["acc_key_hash"] = account_key_hash
    return response


def error_payload(message: str) -> dict[Any, Any]:
    # Client handlers inspect "auth" when expected SRP fields are absent.
    return {"auth": message, "error": [message], "vested_threshold": 5, 0: True}


# The HTTP handler consumes the server-list service, while this name remains a
# compatibility function for older callers and tests.
_SERVER_LIST = ServerListService(CONFIG, v31_read_state, v31_update_state, v39_vessel_ready, server_log)
match_server_list_payload = _SERVER_LIST.response


def capture(
    handler: BaseHTTPRequestHandler,
    body: bytes,
    params: dict[str, list[str]],
    extra: dict[str, Any] | None = None,
    *,
    directory: Path | None = None,
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    record: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "method": handler.command,
        "path": handler.path,
        "client": f"{handler.client_address[0]}:{handler.client_address[1]}",
        "headers": dict(handler.headers.items()),
        "params": params,
        "body_utf8": body.decode("utf-8", errors="replace"),
        "body_hex": body.hex(),
    }
    if extra:
        record.update(extra)
    capture_dir = directory or CAPTURE_DIR
    capture_dir.mkdir(exist_ok=True)
    path = capture_dir / f"{stamp}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ThorGor-SRP/25.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        log(f"{self.client_address[0]} | {fmt % args}")

    def do_GET(self) -> None:
        self.handle_all()

    def do_POST(self) -> None:
        self.handle_all()

    def read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        return self.rfile.read(length) if length > 0 else b""

    def send_php(self, payload: Any) -> None:
        body = php_serialize(payload)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        self.close_connection = True
        log(f"RESPONSE {len(body)}B | {body[:300]!r}")

    def send_text(self, text: str) -> None:
        raw = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def control(self, parsed) -> bool:
        if not parsed.path.startswith("/__"):
            return False

        if parsed.path == "/__status":
            payload = {
                "app": APP_NAME,
                "password_chain": CONFIG.password_chain,
                "salt2": CONFIG.salt2,
                "database": str(CONFIG.database_path),
                "chat_host": CONFIG.chat_host,
                "server_list": (
                    {
                        "class": CONFIG.server_list_class,
                        "ip": CONFIG.server_list_ip,
                        "port": CONFIG.server_list_port,
                    }
                    if CONFIG.server_list_ip
                    else None
                ),
                "server_control_capture_dir": str(SERVER_CAPTURE_DIR),
                "server_control_log": str(SERVER_LOG_PATH),
                "match_control_state": v31_read_state(),
                "account_count": ACCOUNTS.count() if ACCOUNTS else 0,
                "accounts": [
                    {
                        "account_id": account.account_id,
                        "username": account.username,
                        "nickname": account.nickname,
                        "enabled": account.enabled,
                    }
                    for account in (ACCOUNTS.list_accounts() if ACCOUNTS else [])
                ],
                **RUNTIME.status(),
            }
            self.send_text(json.dumps(payload, indent=2) + "\n")
        else:
            self.send_text(
                "Endpoints:\n"
                "  /__status\n"
                "HoN POST fields:\n"
                "  f=pre_auth&login=<name>&A=<hex>\n"
                "  f=srpAuth&login=<name>&proof=<hex>&OSType=...&MajorVersion=...&MinorVersion=...&MicroVersion=...\n"
            )
        return True

    def handle_server_requester(
        self,
        body: bytes,
        params: dict[str, list[str]],
    ) -> None:
        """Capture 3.2.7 game-server/manager control-plane HTTP without guessing.

        This intentionally preserves v24's compatibility behavior for unknown
        requests (a small generic success payload). The point of this build is
        to discover the exact 3.2.7 request functions and fields before adding
        version-specific responses.
        """
        function = params.get("f", [""])[0]
        hint = SERVER_REQUEST_HINTS.get(function, "unknown 3.2.7 server control request")
        generic_response = {"success": 1, "vested_threshold": 5, 0: True}
        response_policy = (
            "v43 exact KONGOR-compatible response"
            if function in {"start_game", "host_lobby", "host_release", "c_conn", "client_auth"}
            else "v24-compatible generic success for unknown requests"
        )

        capture_path = capture(
            self,
            body,
            params,
            {
                "stage": "server_requester",
                "server_function": function,
                "diagnostic_hint": hint,
                "user_agent": self.headers.get("User-Agent", ""),
                "response_policy": response_policy,
            },
            directory=SERVER_CAPTURE_DIR,
        )
        server_log(
            f"REQUEST f={function!r} hint={hint!r} from={self.client_address[0]} "
            f"path={self.path!r} params={json.dumps(params, sort_keys=True)} capture={capture_path.name}"
        )

        # KONGOR-derived control bootstrap. These fields are the bridge from
        # server_requester.php into the chat/control plane; a generic success
        # cannot produce a real registered Idle game-server connection.
        if function == "new_session":
            session = uuid.uuid4().hex
            state = v31_update_state(
                registered=True, idle_confirmed=False, lifecycle="registered",
                server_id=CONFIG.match_server_id, server_session=session,
                server_ip=params.get("ip", [CONFIG.match_server_ip])[0],
                server_port=params.get("port", [str(CONFIG.match_server_port)])[0],
                server_name=params.get("name", ["ThorGor Public"])[0],
                match_id=0, match_date="", match_name="", match_map="",
                match_version="", match_options="",
                pending_host_key="", pending_host_account_id=0,
                pending_host_nickname="", pending_host_reserved_at=0.0,
            )
            response = {
                "session": session, "server_id": CONFIG.match_server_id,
                "chat_address": CONFIG.chat_host, "chat_port": 11031,
                "leaverthreshold": 0.05, "success": 1, 0: True,
            }
            self.send_php(response)
            return
        elif function == "replay_auth":
            session = uuid.uuid4().hex
            v31_update_state(manager_registered=True, manager_session=session, manager_id=1)
            self.send_php({
                "server_id": 1, "official": 1, "session": session,
                "chat_address": CONFIG.chat_host, "chat_port": 11031,
                "success": 1, 0: True,
            })
            return
        elif function == "start_game":
            if ACCOUNTS is None:
                raise RuntimeError("Account database is not initialized")
            state = v31_read_state()
            expected_session = state.get("server_session")
            try:
                existing_match_id = int(state.get("match_id", 0) or 0)
            except (TypeError, ValueError):
                existing_match_id = 0
            try:
                response = start_game_response(
                    ACCOUNTS,
                    params,
                    expected_session,
                    existing_match_id=existing_match_id,
                    existing_match_date=str(state.get("match_date") or ""),
                )
            except ValueError as error:
                server_log(f"START_GAME_REJECTED reason={error}")
                self.send_php({"success": 0, "error": [str(error)]})
                return
            match_id = int(response["match_id"])
            v31_update_state(
                idle_confirmed=False,
                lifecycle="loading",
                match_id=match_id,
                match_date=response["match_date"],
                match_name=params.get("mname", [state.get("match_name") or "Unnamed Game"])[0],
                match_map=params.get("map", [state.get("match_map") or "caldavar"])[0],
                match_version=params.get("version", [state.get("match_version") or "3.2.7.1"])[0],
                match_options=params.get(
                    "options", params.get("game_options", [state.get("match_options") or ""])
                )[0],
            )
            action = "REUSED" if existing_match_id > 0 else "ALLOCATED"
            server_log(
                f"START_GAME_{action} match_id={match_id} "
                f"map={params.get('map', [state.get('match_map') or ''])[0]!r}"
            )
            self.send_php(response)
            return
        elif function == "host_lobby":
            if ACCOUNTS is None:
                raise RuntimeError("Account database is not initialized")
            try:
                identity = client_auth_response(ACCOUNTS, params)
            except ValueError as error:
                server_log(f"HOST_LOBBY_REJECTED reason={error}")
                self.send_php({"success": 0, "error": [str(error)]})
                return
            host_key = params.get("host_key", [""])[0]
            state = v31_read_state()
            pending_key = str(state.get("pending_host_key") or "")
            pending_account_id = int(state.get("pending_host_account_id") or 0)
            try:
                existing_match_id = int(state.get("match_id", 0))
            except (TypeError, ValueError):
                existing_match_id = 0
            if existing_match_id > 0 and hmac.compare_digest(
                str(state.get("match_host_key") or ""), host_key
            ):
                self.send_php({"match_id": existing_match_id, "success": 1})
                return
            if (
                not host_key
                or not pending_key
                or not hmac.compare_digest(host_key, pending_key)
                or identity["account_id"] != pending_account_id
            ):
                server_log("HOST_LOBBY_REJECTED reason=invalid pending host reservation")
                self.send_php({"success": 0, "error": ["Invalid host reservation"]})
                return
            match_id = ACCOUNTS.create_match(
                CONFIG.match_server_id,
                f"c0-host:{host_key}",
                params,
            )
            match_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            v31_update_state(
                idle_confirmed=False,
                lifecycle="lobby",
                match_id=match_id,
                match_date=match_date,
                match_name=params.get("mname", ["Unnamed Game"])[0],
                match_map=params.get("map", ["caldavar"])[0],
                match_version=params.get("version", ["3.2.7.1"])[0],
                match_options=params.get("options", [""])[0],
                match_host_account_id=identity["account_id"],
                match_host_nickname=identity["nickname"],
                match_host_key=host_key,
                pending_host_key="",
                pending_host_account_id=0,
                pending_host_nickname="",
                pending_host_reserved_at=0.0,
                native_start_game_injected=False,
                native_start_game_injected_for=0,
                native_start_game_error="",
            )
            server_log(
                f"HOST_LOBBY_ACTIVATED match_id={match_id} "
                f"name={params.get('mname', [''])[0]!r} map={params.get('map', [''])[0]!r}"
            )
            self.send_php({"match_id": match_id, "match_date": match_date, "success": 1})
            return
        elif function == "host_release":
            if ACCOUNTS is None:
                raise RuntimeError("Account database is not initialized")
            try:
                identity = client_auth_response(ACCOUNTS, params)
            except ValueError as error:
                self.send_php({"success": 0, "error": [str(error)]})
                return
            host_key = params.get("host_key", [""])[0]
            state = v31_read_state()
            pending_key = str(state.get("pending_host_key") or "")
            pending_account_id = int(state.get("pending_host_account_id") or 0)
            if (
                host_key
                and pending_key
                and hmac.compare_digest(host_key, pending_key)
                and identity["account_id"] == pending_account_id
            ):
                v31_update_state(
                    lifecycle="idle",
                    pending_host_key="",
                    pending_host_account_id=0,
                    pending_host_nickname="",
                    pending_host_reserved_at=0.0,
                )
                server_log(f"HOST_RESERVATION_RELEASED account_id={identity['account_id']}")
            self.send_php({"success": 1})
            return
        elif function in {"c_conn", "client_auth"}:
            if ACCOUNTS is None:
                raise RuntimeError("Account database is not initialized")
            try:
                response = client_auth_response(ACCOUNTS, params)
            except ValueError as error:
                server_log(f"CLIENT_AUTH_REJECTED function={function!r} reason={error}")
                self.send_php({"success": 0, "error": [str(error)]})
                return
            state_updates: dict[str, Any] = {
                "last_client_auth_account_id": response["account_id"],
                "last_client_auth_nickname": response["nickname"],
                "last_client_auth_function": function,
            }
            host_key = params.get("host_key", [""])[0]
            if function == "c_conn" and host_key:
                state_updates.update(
                    lifecycle="reserved",
                    pending_host_account_id=response["account_id"],
                    pending_host_nickname=response["nickname"],
                    pending_host_key=host_key,
                    pending_host_reserved_at=time.time(),
                )
                server_log(
                    "C0_HOST_RESERVED "
                    f"host_account_id={response['account_id']} nickname={response['nickname']!r}"
                )
            v31_update_state(**state_updates)
            server_log(
                f"CLIENT_AUTH_ACCEPTED function={function!r} account_id={response['account_id']} "
                f"nickname={response['nickname']!r}"
            )
            self.send_php(response)
            return
        elif function == "shutdown":
            v31_update_state(
                registered=False, idle_confirmed=False, lifecycle="offline",
                match_id=0, match_date="", match_name="", match_map="",
                match_version="", match_options="",
                pending_host_key="", pending_host_account_id=0,
                pending_host_nickname="", pending_host_reserved_at=0.0,
            )

        self.send_php(generic_response)

    def handle_all(self) -> None:
        parsed = urlparse(self.path)
        if self.control(parsed):
            return

        body = self.read_body()
        body_text = body.decode("utf-8", errors="replace")
        params = parse_qs(parsed.query, keep_blank_values=True)

        if "application/x-www-form-urlencoded" in self.headers.get("Content-Type", ""):
            posted = parse_qs(body_text, keep_blank_values=True)
            for key, values in posted.items():
                params.setdefault(key, []).extend(values)

        function = params.get("f", [""])[0]
        username = params.get("login", [""])[0]

        # Account-correlated diagnostic trace for client-facing master calls.
        # Do not log the cookie itself; presence plus resolved identity is enough.
        identity = diagnostic_request_identity(ACCOUNTS, params)
        shared_state = v31_read_state()
        server_log(
            "MASTER_TRACE "
            f"f={function!r} ip={self.client_address[0]} "
            f"login={username!r} account={identity['account']!r} "
            f"account_id={identity['account_id']!r} cookie_present={identity['cookie_present']} "
            f"lifecycle={shared_state.get('lifecycle')!r} match_id={shared_state.get('match_id')!r}"
        )

        if parsed.path.lower().endswith("/server_requester.php"):
            self.handle_server_requester(body, params)
            return

        if function == "pre_auth":
            self.handle_preauth(body, params, username)
        elif function == "srpAuth":
            self.handle_srp_auth(body, params, username)
        elif function == "get_products":
            if ACCOUNTS is None:
                self.send_php(error_payload("Account database unavailable"))
                return
            try:
                response = get_products_response(ACCOUNTS, params)
            except ValueError as error:
                capture(self, body, params, {"stage": "get_products", "error": str(error)})
                self.send_php(error_payload(str(error)))
                return
            auth = diagnostic_request_identity(ACCOUNTS, params)
            capture(
                self,
                body,
                params,
                {
                    "stage": "get_products",
                    "account": auth["account"],
                    "resolved_account_id": auth["account_id"],
                    "supplied_account_id": params.get("account_id", [""])[0],
                    "category_count": len(response["products"]),
                    "category_sizes": {key: len(value) for key, value in response["products"].items()},
                    "crc": response.get("crc"),
                    "lifecycle": v31_read_state().get("lifecycle"),
                    "match_id": v31_read_state().get("match_id"),
                },
            )
            category_sizes = {key: len(value) for key, value in response["products"].items()}
            server_log(
                "PRODUCT_TRACE "
                f"account={auth['account']!r} account_id={auth['account_id']!r} "
                f"categories={len(response['products'])} sizes={category_sizes!r} "
                f"crc={response.get('crc')!r}"
            )
            self.send_php(response)
        elif function in {"matchmaking_join", "matchmaking_poll", "matchmaking_leave"}:
            if MATCHMAKING is None:
                self.send_php(error_payload("Matchmaking service unavailable"))
                return
            try:
                operation = {
                    "matchmaking_join": MATCHMAKING.join,
                    "matchmaking_poll": MATCHMAKING.poll,
                    "matchmaking_leave": MATCHMAKING.leave,
                }[function]
                self.send_php(operation(params))
            except ValueError as error:
                self.send_php(error_payload(str(error)))
        elif function == "server_list":
            cookie = params.get("cookie", [""])[0]
            game_type = params.get("gametype", [""])[0]
            if not cookie:
                self.send_php(error_payload("Missing server_list cookie"))
            elif game_type not in {"10", "90"}:
                self.send_php(error_payload(f"Unknown server_list gametype {game_type!r}"))
            else:
                capture(self, body, params, {"stage": "server_list", "gametype": game_type})
                self.send_php(match_server_list_payload(cookie, game_type))
        else:
            capture(self, body, params, {"stage": "unhandled"})
            self.send_php({"success": 1, "vested_threshold": 5, 0: True})

    def handle_preauth(
        self,
        body: bytes,
        params: dict[str, list[str]],
        username: str,
    ) -> None:
        A_hex = params.get("A", [""])[0].strip()
        if not username or not A_hex:
            self.send_php(error_payload("Missing login or A"))
            return

        if ACCOUNTS is None:
            self.send_php(error_payload("Account database unavailable"))
            return

        account = ACCOUNTS.get(username)
        if account is None or not account.password:
            log(f"PRE_AUTH REJECTED | unknown_or_disabled_user={username!r} ip={self.client_address[0]}")
            capture(self, body, params, {"stage": "pre_auth", "error": "unknown or disabled account"})
            self.send_php(error_payload("Invalid login"))
            return

        try:
            session = create_session(
                username=username,
                password=account.password,
                account_id=account.account_id,
                nickname=account.nickname,
                A_hex=A_hex,
                client_ip=self.client_address[0],
            )
        except Exception as exc:
            log(f"PRE_AUTH ERROR | user={username!r} | {exc}")
            capture(self, body, params, {"stage": "pre_auth", "error": str(exc)})
            self.send_php(error_payload(str(exc)))
            return

        RUNTIME.store(session)
        capture(
            self,
            body,
            params,
            {
                "stage": "pre_auth",
                "password_chain": CONFIG.password_chain,
                "transformed_password": session.transformed_password,
                "A": f"{session.A:0512x}",
                "salt": format(session.salt, "x"),
                "salt2": session.salt2,
                "b": format(session.b, "x"),
                "v": format(session.v, "x"),
                "k": format(session.k, "x"),
                "B": f"{session.B:0512x}",
                "u": format(session.u, "x"),
                "S": format(session.S, "x"),
                "K": session.K.hex(),
                "expected_M1": session.expected_M1.hex(),
                "M2": session.M2.hex(),
            },
        )
        log(
            f"PRE_AUTH | user={username!r} ip={self.client_address[0]} "
            f"chain={CONFIG.password_chain} mixed_csrp_encoding "
            f"expected_M1={session.expected_M1.hex()}"
        )
        self.send_php(preauth_payload(session))

    def handle_srp_auth(
        self,
        body: bytes,
        params: dict[str, list[str]],
        username: str,
    ) -> None:
        supplied_hex = params.get("proof", [""])[0].strip().lower()
        session = RUNTIME.get(self.client_address[0], username)

        if session is None:
            capture(self, body, params, {"stage": "srpAuth", "error": "no session"})
            self.send_php(error_payload("No matching pre_auth session"))
            return

        try:
            supplied = bytes.fromhex(supplied_hex)
        except ValueError:
            supplied = b""

        matched = (
            len(supplied) == 32
            and hmac.compare_digest(supplied, session.expected_M1)
        )

        capture(
            self,
            body,
            params,
            {
                "stage": "srpAuth",
                "password_chain": CONFIG.password_chain,
                "OSType": params.get("OSType", [""])[0],
                "MajorVersion": params.get("MajorVersion", [""])[0],
                "MinorVersion": params.get("MinorVersion", [""])[0],
                "MicroVersion": params.get("MicroVersion", [""])[0],
                "supplied_M1": supplied_hex,
                "expected_M1": session.expected_M1.hex(),
                "matched": matched,
                "M2": session.M2.hex(),
            },
        )

        log(
            f"SRP_AUTH | user={username!r} ip={self.client_address[0]} "
            f"supplied={supplied_hex} expected={session.expected_M1.hex()} "
            f"MATCH={matched}"
        )

        if not matched:
            self.send_php(error_payload("SRP proof mismatch"))
            return

        RUNTIME.consume(self.client_address[0], username)
        if ACCOUNTS is None:
            raise RuntimeError("Account database is not initialized")
        authorization = ACCOUNTS.register_game_authorization(session.account_id)
        log(f"***** SRP AUTHENTICATION SUCCESSFUL: {username!r} *****")
        self.send_php(success_payload(session, authorization.cookie))


class Server(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--database",
        default=str(BASE_DIR / "thorgor_accounts.db"),
        help="SQLite account database path.",
    )
    parser.add_argument(
        "--add-account",
        nargs=2,
        metavar=("USERNAME", "PASSWORD"),
        help="Create or update a local account, then exit.",
    )
    parser.add_argument(
        "--add-account-env",
        nargs=2,
        metavar=("USERNAME", "ENVIRONMENT_VARIABLE"),
        help="Create or update an account using a password read from an environment variable, then exit.",
    )
    parser.add_argument(
        "--nickname",
        help="Optional nickname used with --add-account.",
    )
    parser.add_argument(
        "--list-accounts",
        action="store_true",
        help="List local accounts, then exit.",
    )
    parser.add_argument(
        "--disable-account",
        metavar="USERNAME",
        help="Disable an account, then exit.",
    )
    parser.add_argument(
        "--enable-account",
        metavar="USERNAME",
        help="Enable an account, then exit.",
    )
    parser.add_argument(
        "--delete-account",
        metavar="USERNAME",
        help="Delete an account, then exit.",
    )
    parser.add_argument(
        "--salt2",
        default="p^^^&bjRlXi4B=A1y.@Vz)",
        help="salt2 returned during pre_auth.",
    )
    parser.add_argument(
        "--password-chain",
        choices=("direct", "pre-md5"),
        default="pre-md5",
        help="Credential preprocessing. 'pre-md5' is required by the verified HoN 3.2.7.1 client capture.",
    )
    parser.add_argument(
        "--session-ttl",
        type=int,
        default=300,
        help="Seconds before an unfinished pre_auth session expires.",
    )
    parser.add_argument(
        "--chat-host",
        default="127.0.0.1",
        help="Chat host returned after login. Use a LAN or public address for remote clients.",
    )
    parser.add_argument(
        "--server-list-ip",
        default="",
        help="Optional IP advertised to the client's UDP public-game browser.",
    )
    parser.add_argument(
        "--server-list-port",
        type=int,
        default=11236,
        help="UDP public-game browser port advertised with --server-list-ip.",
    )
    parser.add_argument(
        "--server-list-class",
        type=int,
        default=1,
        help="Legacy integer class attached to the advertised server-list entry.",
    )
    parser.add_argument(
        "--match-server-id",
        type=int,
        default=1,
        help="Numeric match-server ID shown in the public-game create-server picker.",
    )
    parser.add_argument(
        "--match-server-ip",
        default="127.0.0.1",
        help="Match-server IP shown in the public-game create-server picker.",
    )
    parser.add_argument(
        "--match-server-port",
        type=int,
        default=11235,
        help="Real original slave UDP game port (the CREATE picker is intentionally routed through --server-list-port).",
    )
    parser.add_argument(
        "--match-server-location",
        default="USE",
        help="Region/location code shown in the public-game create-server picker.",
    )
    args = parser.parse_args(argv)

    if not 1 <= args.server_list_port <= 65535:
        parser.error("--server-list-port must be between 1 and 65535")
    if not 1 <= args.match_server_port <= 65535:
        parser.error("--match-server-port must be between 1 and 65535")

    global ACCOUNTS, MATCHMAKING
    CONFIG.salt2 = args.salt2
    CONFIG.password_chain = args.password_chain
    CONFIG.session_ttl = max(30, args.session_ttl)
    CONFIG.database_path = Path(args.database).expanduser().resolve()
    CONFIG.chat_host = args.chat_host
    CONFIG.server_list_ip = args.server_list_ip
    CONFIG.server_list_port = args.server_list_port
    CONFIG.server_list_class = args.server_list_class
    CONFIG.match_server_id = args.match_server_id
    CONFIG.match_server_ip = args.match_server_ip
    CONFIG.match_server_port = args.match_server_port
    CONFIG.match_server_location = args.match_server_location
    ACCOUNTS = AccountStore(CONFIG.database_path)
    MATCHMAKING = MatchmakingEndpoint(
        ACCOUNTS,
        DedicatedServerAllocator(
            ACCOUNTS, v31_read_state, v31_update_state, v39_vessel_ready,
            server_id=CONFIG.match_server_id,
            host=CONFIG.server_list_ip or CONFIG.match_server_ip,
            port=CONFIG.server_list_port,
        ),
    )

    if args.add_account:
        account = ACCOUNTS.add_or_update(args.add_account[0], args.add_account[1], args.nickname)
        print(f"Saved account #{account.account_id}: {account.username!r} nickname={account.nickname!r}")
        return 0
    if args.add_account_env:
        username, variable = args.add_account_env
        password = os.environ.get(variable, "")
        if not password:
            parser.error(f"environment variable {variable!r} is empty or undefined")
        account = ACCOUNTS.add_or_update(username, password, args.nickname)
        print(f"Saved account #{account.account_id}: {account.username!r} nickname={account.nickname!r}")
        return 0
    if args.list_accounts:
        accounts = ACCOUNTS.list_accounts()
        if not accounts:
            print("No accounts in database.")
        for account in accounts:
            state = "enabled" if account.enabled else "disabled"
            print(f"{account.account_id:4d}  {account.username:<24} {state:<8} nickname={account.nickname!r}")
        return 0
    if args.disable_account:
        print("Disabled." if ACCOUNTS.set_enabled(args.disable_account, False) else "Account not found.")
        return 0
    if args.enable_account:
        print("Enabled." if ACCOUNTS.set_enabled(args.enable_account, True) else "Account not found.")
        return 0
    if args.delete_account:
        print("Deleted." if ACCOUNTS.delete(args.delete_account) else "Account not found.")
        return 0

    if ACCOUNTS.count() == 0:
        account = ACCOUNTS.add_or_update("pwnrbwnr", "test123", "pwnrbwnr")
        print(f"Created starter account #{account.account_id}: pwnrbwnr / test123")
    else:
        missing = [a.username for a in ACCOUNTS.list_accounts() if not a.password]
        if missing:
            print("WARNING: v20 accounts need their passwords re-entered before login:")
            for name in missing:
                print(f"  - {name}")

    try:
        server = Server((args.host, args.port), Handler)
    except OSError as exc:
        print(f"Could not bind {args.host}:{args.port}: {exc}", file=sys.stderr)
        print(
            "Run PowerShell as Administrator and check: "
            "netstat -ano | findstr :80",
            file=sys.stderr,
        )
        return 1

    print("=" * 92)
    print(APP_NAME)
    print(f"Listening: http://127.0.0.1:{args.port}")
    print(f"Account database: {CONFIG.database_path}")
    print(f"Configured accounts: {ACCOUNTS.count()}")
    print(f"salt2: {CONFIG.salt2!r}")
    print(f"Password chain: {CONFIG.password_chain}")
    print(f"Chat host: {CONFIG.chat_host}")
    if CONFIG.server_list_ip:
        print(
            "Server-list advertisement: "
            f"class={CONFIG.server_list_class} "
            f"{CONFIG.server_list_ip}:{CONFIG.server_list_port}"
        )
    else:
        print("Server-list advertisement: disabled")
    if CONFIG.match_server_ip:
        print(
            "Public CREATE picker row: "
            f"id={CONFIG.match_server_id} "
            f"{CONFIG.server_list_ip or CONFIG.match_server_ip}:{CONFIG.server_list_port} "
            f"location={CONFIG.match_server_location}"
        )
        print(
            "Real original slave target: "
            f"{CONFIG.match_server_ip}:{CONFIG.match_server_port}"
        )
    else:
        print("Public create-server picker: disabled")
    print("SRP integer encoding: exact mixed HoN/CSRP rules")
    print(f"SRP/client captures: {CAPTURE_DIR}")
    print(f"Server-control captures: {SERVER_CAPTURE_DIR}")
    print(f"Server-control log: {SERVER_LOG_PATH}")
    print(f"Log: {LOG_PATH}")
    print("Status: http://127.0.0.1/__status")
    print("-" * 92)
    print("Recovered request shapes:")
    print("  f=pre_auth&login=<name>&A=<512 hex chars>")
    print("  f=srpAuth&login=<name>&proof=<64 hex chars>&OSType=...&MajorVersion=...&MinorVersion=...&MicroVersion=...")
    print("  /server_requester.php: every request is raw-captured for control-plane discovery")
    print("=" * 92)

    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    _write_startup_marker()
    raise SystemExit(main())
