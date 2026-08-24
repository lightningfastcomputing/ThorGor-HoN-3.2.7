"""Persistent LAN friend requests and protocol-47 social notifications."""
from __future__ import annotations

import secrets
import struct
from collections.abc import Callable

from thorgor.chat.protocol import cstr
from thorgor.master.accounts import Account, AccountStore

FRIEND_REQUEST = 0x000D
FRIEND_APPROVE = 0x00B3
FRIEND_REQUEST_RESPONSE = 0x00B2
FRIEND_APPROVE_RESPONSE = 0x00B4

Sender = Callable[[int, int, bytes], bool]
OnlineCheck = Callable[[int], bool]


class SocialService:
    def __init__(self, store: AccountStore, send: Sender, online: OnlineCheck) -> None:
        self.store = store
        self.send = send
        self.online = online
        with self.store.lock, self.store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS friend_requests (
                requester_id INTEGER NOT NULL, target_id INTEGER NOT NULL,
                notification_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (requester_id, target_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS friends (
                account_id INTEGER NOT NULL, friend_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, friend_id))""")
            db.commit()

    def _account(self, *, account_id: int | None = None,
                 name: str | None = None) -> Account | None:
        name_folded = name.casefold() if name is not None else None
        return next((account for account in self.store.list_accounts()
                     if (account_id is not None and account.account_id == account_id)
                     or (name_folded is not None and
                         (account.username.casefold() == name_folded
                          or account.nickname.casefold() == name_folded))), None)

    @staticmethod
    def _request_payload(status: int, notification_id: int, account: Account,
                         online: bool) -> bytes:
        return (
            bytes((status,)) + struct.pack("<i", notification_id) + cstr(account.nickname)
            + struct.pack("<I", account.account_id) + bytes((0 if online else 1, 0))
            + struct.pack("<I", 0) + cstr("") + cstr("") + cstr("") + cstr("")
            + struct.pack("<I", 0)
        )

    @staticmethod
    def _failure(target_name: str) -> bytes:
        return b"\x00" + struct.pack("<i", 0) + cstr(target_name)

    def request(self, requester_id: int, target_name: str) -> bool:
        requester = self._account(account_id=requester_id)
        target = self._account(name=target_name)
        if requester is None or target is None or requester.account_id == target.account_id:
            if requester is not None:
                self.send(requester_id, FRIEND_REQUEST_RESPONSE, self._failure(target_name))
            return False
        with self.store.lock, self.store.connect() as db:
            already = db.execute(
                "SELECT 1 FROM friends WHERE account_id=? AND friend_id=?",
                (requester_id, target.account_id),
            ).fetchone()
            pending = db.execute(
                "SELECT notification_id FROM friend_requests WHERE requester_id=? AND target_id=?",
                (requester_id, target.account_id),
            ).fetchone()
            if already or pending:
                payload = b"\x03" + struct.pack("<i", 0) + cstr(target.nickname)
                self.send(requester_id, FRIEND_REQUEST_RESPONSE, payload)
                return False
            notification_id = secrets.randbelow(0x7FFFFFFE) + 1
            db.execute(
                "INSERT INTO friend_requests (requester_id,target_id,notification_id) VALUES (?,?,?)",
                (requester_id, target.account_id, notification_id),
            )
            db.commit()
        self.send(
            requester_id, FRIEND_REQUEST_RESPONSE,
            self._request_payload(1, 0, target, self.online(target.account_id)),
        )
        self.send(
            target.account_id, FRIEND_REQUEST_RESPONSE,
            self._request_payload(2, notification_id, requester, True),
        )
        return True

    def approve(self, approver_id: int, requester_name: str) -> bool:
        approver = self._account(account_id=approver_id)
        requester = self._account(name=requester_name)
        if approver is None or requester is None:
            return False
        with self.store.lock, self.store.connect() as db:
            row = db.execute(
                "SELECT notification_id FROM friend_requests WHERE requester_id=? AND target_id=?",
                (requester.account_id, approver_id),
            ).fetchone()
            if row is None:
                payload = b"\x00" + struct.pack("<Ii", requester.account_id, 0) + cstr(requester_name)
                self.send(approver_id, FRIEND_APPROVE_RESPONSE, payload)
                return False
            notification_id = int(row[0])
            db.execute("INSERT OR IGNORE INTO friends (account_id,friend_id) VALUES (?,?)",
                       (approver_id, requester.account_id))
            db.execute("INSERT OR IGNORE INTO friends (account_id,friend_id) VALUES (?,?)",
                       (requester.account_id, approver_id))
            db.execute("DELETE FROM friend_requests WHERE requester_id=? AND target_id=?",
                       (requester.account_id, approver_id))
            db.commit()
        self.send(
            approver_id, FRIEND_APPROVE_RESPONSE,
            b"\x01" + struct.pack("<Ii", requester.account_id, notification_id)
            + cstr(requester.nickname),
        )
        self.send(
            requester.account_id, FRIEND_APPROVE_RESPONSE,
            b"\x02" + struct.pack("<Ii", approver_id, 0) + cstr(approver.nickname),
        )
        return True

    def deliver_pending(self, target_id: int) -> None:
        with self.store.lock, self.store.connect() as db:
            rows = db.execute(
                "SELECT requester_id,notification_id FROM friend_requests WHERE target_id=?",
                (target_id,),
            ).fetchall()
        for requester_id, notification_id in rows:
            requester = self._account(account_id=int(requester_id))
            if requester is not None:
                self.send(
                    target_id, FRIEND_REQUEST_RESPONSE,
                    self._request_payload(2, int(notification_id), requester,
                                          self.online(requester.account_id)),
                )
