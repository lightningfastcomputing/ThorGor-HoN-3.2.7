"""Thread-safe ownership of unfinished SRP authentication sessions."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
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
    def __init__(self, ttl: int | Callable[[], int] = 300) -> None:
        self.lock = threading.Lock()
        self.sessions: dict[tuple[str, str], Session] = {}
        self._ttl = ttl

    @property
    def ttl(self) -> int:
        return int(self._ttl() if callable(self._ttl) else self._ttl)

    def cleanup(self) -> None:
        cutoff = time.time() - self.ttl
        for key in [key for key, value in self.sessions.items() if value.created_at < cutoff]:
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

    def status(self) -> dict[str, object]:
        with self.lock:
            self.cleanup()
            return {"active_sessions": len(self.sessions), "sessions": [
                {"client_ip": session.client_ip, "username": session.username,
                 "age_seconds": round(time.time() - session.created_at, 3)}
                for session in self.sessions.values()
            ]}


__all__ = ["Session", "Runtime"]
