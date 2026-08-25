"""Persistent LAN accounts and game authorization records."""
from __future__ import annotations

import secrets
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

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
    """Single owner of accounts, issued cookies, and persistent match IDs."""
    def __init__(self, path: Path) -> None:
        self.path, self.lock = path, threading.RLock()
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try: yield db
        finally: db.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock, self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS accounts (
                account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                transformed_password TEXT, password TEXT, nickname TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("""CREATE TABLE IF NOT EXISTS game_authorizations (
                account_id INTEGER PRIMARY KEY, cookie TEXT NOT NULL UNIQUE,
                game_cookie TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("""CREATE TABLE IF NOT EXISTS matches (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT, server_id INTEGER NOT NULL,
                server_session TEXT NOT NULL, map TEXT NOT NULL DEFAULT '',
                version TEXT NOT NULL DEFAULT '', match_name TEXT NOT NULL DEFAULT '',
                casual TEXT NOT NULL DEFAULT '', match_mode TEXT NOT NULL DEFAULT '',
                accounts TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("""CREATE TABLE IF NOT EXISTS friend_requests (
                requester_id INTEGER NOT NULL, target_id INTEGER NOT NULL,
                notification_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (requester_id, target_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS friends (
                account_id INTEGER NOT NULL, friend_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, friend_id))""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(accounts)")}
            if "password" not in columns: db.execute("ALTER TABLE accounts ADD COLUMN password TEXT")
            db.commit()

    @staticmethod
    def _account(row: sqlite3.Row) -> Account:
        return Account(int(row["account_id"]), str(row["username"]), str(row["password"] or ""),
                       str(row["nickname"]), bool(row["enabled"]))

    def add_or_update(self, username: str, password: str, nickname: str | None = None) -> Account:
        username = username.strip()
        if not username: raise ValueError("Username cannot be empty")
        if not password: raise ValueError("Password cannot be empty")
        nickname = (nickname or username).strip() or username
        with self.lock, self.connect() as db:
            db.execute("""INSERT INTO accounts (username,transformed_password,password,nickname,enabled)
                VALUES (?,NULL,?,?,1) ON CONFLICT(username) DO UPDATE SET
                transformed_password=NULL,password=excluded.password,nickname=excluded.nickname,
                enabled=1,updated_at=CURRENT_TIMESTAMP""", (username, password, nickname))
            db.commit()
        result = self.get(username, include_disabled=True)
        if result is None: raise RuntimeError("Account was not saved")
        return result

    def get(self, username: str, *, include_disabled: bool = False) -> Account | None:
        query = "SELECT account_id,username,password,nickname,enabled FROM accounts WHERE username=?"
        if not include_disabled: query += " AND enabled=1"
        with self.lock, self.connect() as db: row = db.execute(query, (username,)).fetchone()
        return None if row is None else self._account(row)

    def register_game_authorization(self, account_id: int) -> GameAuthorization:
        cookie, game_cookie = f"THORGOR_LOCAL_COOKIE_{account_id:08d}", secrets.token_hex(16)
        with self.lock, self.connect() as db:
            row = db.execute("SELECT account_id,username,password,nickname,enabled FROM accounts WHERE account_id=? AND enabled=1", (account_id,)).fetchone()
            if row is None: raise ValueError("Cannot authorize an unknown or disabled account")
            db.execute("""INSERT INTO game_authorizations (account_id,cookie,game_cookie) VALUES (?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET cookie=excluded.cookie,
                game_cookie=excluded.game_cookie,updated_at=CURRENT_TIMESTAMP""", (account_id, cookie, game_cookie))
            db.commit()
        return GameAuthorization(self._account(row), cookie, game_cookie)

    def get_game_authorization(self, cookie: str) -> GameAuthorization | None:
        with self.lock, self.connect() as db:
            row = db.execute("""SELECT a.account_id,a.username,a.password,a.nickname,a.enabled,g.cookie,g.game_cookie
                FROM game_authorizations g JOIN accounts a ON a.account_id=g.account_id
                WHERE g.cookie=? AND a.enabled=1""", (cookie,)).fetchone()
        return None if row is None else GameAuthorization(self._account(row), str(row["cookie"]), str(row["game_cookie"]))

    def create_match(self, server_id: int, server_session: str, params: dict[str, list[str]]) -> int:
        get = lambda key: params.get(key, [""])[0]
        with self.lock, self.connect() as db:
            cursor = db.execute("""INSERT INTO matches (server_id,server_session,map,version,match_name,casual,match_mode,accounts)
                VALUES (?,?,?,?,?,?,?,?)""", (server_id, server_session, get("map"), get("version"), get("mname"), get("casual"), get("match_mode"), get("accounts")))
            db.commit(); match_id = int(cursor.lastrowid)
        if match_id <= 0: raise RuntimeError("SQLite did not allocate a positive match ID")
        return match_id

    def list_accounts(self) -> list[Account]:
        with self.lock, self.connect() as db: rows = db.execute("SELECT account_id,username,password,nickname,enabled FROM accounts ORDER BY account_id").fetchall()
        return [self._account(row) for row in rows]

    def approve_friend_notification(self, target_id: int, notification_id: int) -> Account | None:
        """Atomically accept the pending request represented by a master notification."""
        with self.lock, self.connect() as db:
            row = db.execute("""SELECT a.account_id,a.username,a.password,a.nickname,a.enabled
                FROM friend_requests r JOIN accounts a ON a.account_id=r.requester_id
                WHERE r.target_id=? AND r.notification_id=?""",
                (target_id, notification_id)).fetchone()
            if row is None:
                return None
            requester = self._account(row)
            db.execute("INSERT OR IGNORE INTO friends (account_id,friend_id) VALUES (?,?)",
                       (target_id, requester.account_id))
            db.execute("INSERT OR IGNORE INTO friends (account_id,friend_id) VALUES (?,?)",
                       (requester.account_id, target_id))
            db.execute("DELETE FROM friend_requests WHERE target_id=? AND notification_id=?",
                       (target_id, notification_id))
            db.commit()
            return requester

    def list_friends(self, account_id: int) -> list[Account]:
        with self.lock, self.connect() as db:
            rows = db.execute("""SELECT a.account_id,a.username,a.password,a.nickname,a.enabled
                FROM friends f JOIN accounts a ON a.account_id=f.friend_id
                WHERE f.account_id=? AND a.enabled=1 ORDER BY a.nickname COLLATE NOCASE""",
                (account_id,)).fetchall()
        return [self._account(row) for row in rows]

    def pending_friend_notifications(self, target_id: int) -> list[tuple[Account, int, str]]:
        with self.lock, self.connect() as db:
            rows = db.execute("""SELECT a.account_id,a.username,a.password,a.nickname,a.enabled,
                    r.notification_id,r.created_at
                FROM friend_requests r JOIN accounts a ON a.account_id=r.requester_id
                WHERE r.target_id=? ORDER BY r.created_at,r.requester_id""",
                (target_id,)).fetchall()
        return [(self._account(row), int(row["notification_id"]), str(row["created_at"]))
                for row in rows]

    def set_enabled(self, username: str, enabled: bool) -> bool:
        with self.lock, self.connect() as db:
            cursor = db.execute("UPDATE accounts SET enabled=?,updated_at=CURRENT_TIMESTAMP WHERE username=?", (int(enabled), username)); db.commit()
        return cursor.rowcount > 0

    def delete(self, username: str) -> bool:
        with self.lock, self.connect() as db:
            cursor = db.execute("DELETE FROM accounts WHERE username=?", (username,)); db.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        with self.lock, self.connect() as db: return int(db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0])

__all__ = ["Account", "GameAuthorization", "AccountStore"]
