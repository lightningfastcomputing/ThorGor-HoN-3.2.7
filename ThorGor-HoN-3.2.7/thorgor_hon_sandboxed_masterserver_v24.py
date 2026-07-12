#!/usr/bin/env python3
"""
ThorGor HoN Sandboxed Masterserver v24

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
import secrets
import sqlite3
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

APP_NAME = "ThorGor HoN Sandboxed Masterserver v24"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 80

BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = BASE_DIR / "thorgor_srp_v24.log"
CAPTURE_DIR = BASE_DIR / "thorgor_srp_v24_captures"
CAPTURE_DIR.mkdir(exist_ok=True)

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


class Config:
    salt2 = "p^^^&bjRlXi4B=A1y.@Vz)"
    password_chain = "pre-md5"
    session_ttl = 300
    database_path = BASE_DIR / "thorgor_accounts.db"


CONFIG = Config()


@dataclass(frozen=True)
class Account:
    account_id: int
    username: str
    password: str
    nickname: str
    enabled: bool


class AccountStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.RLock()
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

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


ACCOUNTS: AccountStore | None = None


def php_serialize(value: Any) -> bytes:
    if value is None:
        return b"N;"
    if value is True:
        return b"b:1;"
    if value is False:
        return b"b:0;"
    if isinstance(value, int):
        return f"i:{value};".encode("ascii")
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


RUNTIME = Runtime()


def log(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    line = f"{stamp} | {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


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


def success_payload(session: Session) -> dict[Any, Any]:
    """
    Minimal typed account payload reconstructed from FUN_15317110.

    The legacy parser expects numeric fields as PHP integers, not numeric
    strings. Earlier builds used strings for account_id/account_type/trial,
    which could make GetInteger() return -1 or corrupt later state.

    Optional nested collections are omitted so their parser branches are
    skipped cleanly.
    """
    return {
        "proof": session.M2.hex(),

        # Required account gate.
        "account_id": session.account_id,
        "auth": "Authorized",
        "account_type": 5,

        # Required identity/session strings.
        "nickname": session.nickname,
        "email": "",
        "ip": "127.0.0.1",
        "cookie": f"THORGOR_LOCAL_COOKIE_{session.account_id:08d}",
        "auth_hash": hashlib.sha1(f"THORGOR_LOCAL_AUTH:{session.account_id}:{session.username}".encode("utf-8")).hexdigest(),

        # Safe scalar defaults read directly by FUN_15317110.
        "show_purchase": False,
        "standing": 3,
        "vested_threshold": 5,
        "pass_exp": "",
        "chat_url": "127.0.0.1",
        "mute_expiration": 0,
        "leaverthreshold": 0.0,
        "minimum_ranked_level": 0.0,
        "is_subaccount": False,

        0: True,
    }


def error_payload(message: str) -> dict[Any, Any]:
    # Client handlers inspect "auth" when expected SRP fields are absent.
    return {"auth": message, "error": [message], "vested_threshold": 5, 0: True}


def capture(
    handler: BaseHTTPRequestHandler,
    body: bytes,
    params: dict[str, list[str]],
    extra: dict[str, Any] | None = None,
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
    path = CAPTURE_DIR / f"{stamp}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ThorGor-SRP/23.0"

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

        if function == "pre_auth":
            self.handle_preauth(body, params, username)
        elif function == "srpAuth":
            self.handle_srp_auth(body, params, username)
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
        log(f"***** SRP AUTHENTICATION SUCCESSFUL: {username!r} *****")
        self.send_php(success_payload(session))


class Server(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
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
    args = parser.parse_args()

    global ACCOUNTS
    CONFIG.salt2 = args.salt2
    CONFIG.password_chain = args.password_chain
    CONFIG.session_ttl = max(30, args.session_ttl)
    CONFIG.database_path = Path(args.database).expanduser().resolve()
    ACCOUNTS = AccountStore(CONFIG.database_path)

    if args.add_account:
        account = ACCOUNTS.add_or_update(args.add_account[0], args.add_account[1], args.nickname)
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
    print("SRP integer encoding: exact mixed HoN/CSRP rules")
    print(f"Captures: {CAPTURE_DIR}")
    print(f"Log: {LOG_PATH}")
    print("Status: http://127.0.0.1/__status")
    print("-" * 92)
    print("Recovered request shapes:")
    print("  f=pre_auth&login=<name>&A=<512 hex chars>")
    print("  f=srpAuth&login=<name>&proof=<64 hex chars>&OSType=...&MajorVersion=...&MinorVersion=...&MicroVersion=...")
    print("=" * 92)

    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
