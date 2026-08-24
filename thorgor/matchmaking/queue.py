from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class MatchRequest:
    account_id: int
    nickname: str
    mode: str = "allpick"
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MatchQueue:
    """A deterministic FIFO queue for the first LAN matchmaking milestone."""

    def __init__(self) -> None:
        self._requests: deque[MatchRequest] = deque()
        self._accounts: set[int] = set()
        self._lock = threading.RLock()

    def join(self, request: MatchRequest) -> bool:
        with self._lock:
            if request.account_id in self._accounts:
                return False
            self._requests.append(request)
            self._accounts.add(request.account_id)
            return True

    def leave(self, account_id: int) -> bool:
        with self._lock:
            if account_id not in self._accounts:
                return False
            self._requests = deque(r for r in self._requests if r.account_id != account_id)
            self._accounts.remove(account_id)
            return True

    def take(self, count: int, mode: str) -> tuple[MatchRequest, ...]:
        if count < 1:
            raise ValueError("count must be positive")
        with self._lock:
            selected = [r for r in self._requests if r.mode.casefold() == mode.casefold()][:count]
            if len(selected) != count:
                return ()
            ids = {r.account_id for r in selected}
            self._requests = deque(r for r in self._requests if r.account_id not in ids)
            self._accounts.difference_update(ids)
            return tuple(selected)

    def restore_front(self, requests: tuple[MatchRequest, ...]) -> None:
        """Restore a failed allocation without changing the original FIFO order."""
        with self._lock:
            for request in reversed(requests):
                if request.account_id not in self._accounts:
                    self._requests.appendleft(request)
                    self._accounts.add(request.account_id)

    def snapshot(self, mode: str | None = None) -> tuple[MatchRequest, ...]:
        with self._lock:
            if mode is None:
                return tuple(self._requests)
            return tuple(r for r in self._requests if r.mode.casefold() == mode.casefold())
