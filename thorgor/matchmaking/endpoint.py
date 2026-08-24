"""Authenticated LAN matchmaking endpoint and dedicated-server allocation."""
from __future__ import annotations

from dataclasses import asdict
import threading
from typing import Callable

from thorgor.master.accounts import AccountStore

from .game_assignment import GameAssignment
from .matchmaker import Matchmaker
from .queue import MatchQueue, MatchRequest

StateReader = Callable[[], dict[str, object]]
StateUpdater = Callable[..., dict[str, object]]
ReadyCheck = Callable[[], bool]


class DedicatedServerAllocator:
    """Atomically claims the one proven HoN slave represented by shared state."""

    def __init__(self, store: AccountStore, read_state: StateReader, update_state: StateUpdater,
                 ready: ReadyCheck, *, server_id: int, host: str, port: int) -> None:
        self.store = store
        self.read_state = read_state
        self.update_state = update_state
        self.ready = ready
        self.server_id = server_id
        self.host = host
        self.port = port

    def __call__(self, _candidate_id: int, mode: str,
                 account_ids: tuple[int, ...]) -> tuple[int, str, str, int]:
        state = self.read_state()
        if not self.ready() or str(state.get("lifecycle", "idle")) not in {"idle", "registered"}:
            raise RuntimeError("no idle dedicated server is available")
        if int(state.get("match_id", 0) or 0) > 0:
            raise RuntimeError("dedicated server already owns a match")
        params = {
            "map": ["caldavar"], "version": ["3.2.7.1"],
            "mname": [f"ThorGor Matchmaking {mode}"], "match_mode": [mode],
            "accounts": [",".join(str(value) for value in account_ids)],
        }
        match_id = self.store.create_match(self.server_id, f"matchmaking:{mode}", params)
        self.update_state(
            lifecycle="allocated", idle_confirmed=False, match_id=match_id,
            match_name=params["mname"][0], match_map="caldavar", match_version="3.2.7.1",
            match_options=f"mode:{mode}", matchmaking_accounts=list(account_ids),
        )
        return match_id, str(self.server_id), self.host, self.port


class MatchmakingEndpoint:
    """A real master HTTP boundary for queue, poll, and leave operations."""

    def __init__(self, store: AccountStore, allocator: DedicatedServerAllocator,
                 *, players_per_match: int = 2) -> None:
        self.store = store
        self.players_per_match = players_per_match
        self.queue = MatchQueue()
        self.matchmaker = Matchmaker(self.queue, allocator)
        self.assignments: dict[int, GameAssignment] = {}
        self._lock = threading.RLock()

    def _identity(self, params: dict[str, list[str]]):
        cookie = params.get("cookie", [""])[0]
        authorization = self.store.get_game_authorization(cookie) if cookie else None
        if authorization is None:
            raise ValueError("Invalid player cookie")
        return authorization.account

    @staticmethod
    def _payload(status: str, assignment: GameAssignment | None = None, **extra):
        result: dict[str, object] = {"success": 1, "status": status, **extra}
        if assignment is not None:
            result["assignment"] = {
                **asdict(assignment),
                "account_ids": list(assignment.account_ids),
            }
        return result

    def join(self, params: dict[str, list[str]]) -> dict[str, object]:
        with self._lock:
            account = self._identity(params)
            existing = self.assignments.get(account.account_id)
            if existing is not None:
                return self._payload("assigned", existing)
            mode = params.get("mode", ["allpick"])[0].casefold() or "allpick"
            joined = self.queue.join(MatchRequest(account.account_id, account.nickname, mode))
            try:
                assignment = self.matchmaker.form_match(mode, self.players_per_match)
            except RuntimeError as exc:
                return self._payload("queued", position=self._position(account.account_id), detail=str(exc))
            if assignment is not None:
                for account_id in assignment.account_ids:
                    self.assignments[account_id] = assignment
            assignment = self.assignments.get(account.account_id)
            return self._payload("assigned", assignment) if assignment else self._payload(
                "queued", position=self._position(account.account_id), duplicate=not joined
            )

    def poll(self, params: dict[str, list[str]]) -> dict[str, object]:
        with self._lock:
            account = self._identity(params)
            assignment = self.assignments.get(account.account_id)
            if assignment:
                return self._payload("assigned", assignment)
            position = self._position(account.account_id)
            return self._payload("queued" if position else "idle", position=position)

    def leave(self, params: dict[str, list[str]]) -> dict[str, object]:
        with self._lock:
            account = self._identity(params)
            removed = self.queue.leave(account.account_id)
            return self._payload("left", removed=removed)

    def _position(self, account_id: int) -> int:
        return next((index for index, request in enumerate(self.queue.snapshot(), 1)
                     if request.account_id == account_id), 0)
