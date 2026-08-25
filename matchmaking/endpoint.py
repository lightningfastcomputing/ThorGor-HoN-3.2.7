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
        is_botmatch = mode.casefold() == "botmatch"
        match_mode = "botmatch" if is_botmatch else "normal"
        match_options = (
            "map:caldavar teamsize:5 mode:botmatch casual:true allheroes:true "
            "noleaver:false spectators:1 randombots:4|5 allowduplicate:true "
            "noagility:false nostrength:false nointelligence:false"
            if is_botmatch else
            "map:caldavar teamsize:1 mode:normal allheroes:true noleaver:false spectators:2"
        )
        params = {
            "map": ["caldavar"], "version": ["3.2.7.1"],
            "mname": [f"ThorGor Matchmaking {mode}"], "match_mode": [match_mode],
            "accounts": [",".join(str(value) for value in account_ids)],
        }
        match_id = self.store.create_match(self.server_id, f"matchmaking:{mode}", params)
        self.update_state(
            lifecycle="allocated", idle_confirmed=False, match_id=match_id,
            match_name=params["mname"][0], match_map="caldavar", match_version="3.2.7.1",
            match_options=match_options, matchmaking_accounts=list(account_ids),
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
        account = self._identity(params)
        mode = params.get("mode", ["allpick"])[0].casefold() or "allpick"
        return self.join_account(account.account_id, account.nickname, mode)

    def join_account(self, account_id: int, nickname: str, mode: str,
                     *, players_per_match: int | None = None) -> dict[str, object]:
        """Queue an identity already authenticated by the chat or master boundary."""
        with self._lock:
            existing = self.assignments.get(account_id)
            if existing is not None:
                return self._payload("assigned", existing)
            joined = self.queue.join(MatchRequest(account_id, nickname, mode))
            assignment = self._try_assign_locked(
                mode, players_per_match or self.players_per_match
            )
            assignment = self.assignments.get(account_id) or assignment
            return self._payload("assigned", assignment) if assignment else self._payload(
                "queued", position=self._position(account_id), duplicate=not joined
            )

    def try_assign(self, mode: str, players_per_match: int | None = None) -> GameAssignment | None:
        with self._lock:
            return self._try_assign_locked(mode, players_per_match or self.players_per_match)

    def _try_assign_locked(self, mode: str, players: int) -> GameAssignment | None:
        try:
            assignment = self.matchmaker.form_match(mode, players)
        except RuntimeError:
            return None
        if assignment is not None:
            for account_id in assignment.account_ids:
                self.assignments[account_id] = assignment
        return assignment

    def assignment_for(self, account_id: int) -> GameAssignment | None:
        with self._lock:
            return self.assignments.get(account_id)

    def leave_account(self, account_id: int) -> bool:
        with self._lock:
            return self.queue.leave(account_id)

    def reset_account(self, account_id: int) -> None:
        with self._lock:
            self.queue.leave(account_id)
            self.assignments.pop(account_id, None)

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
            removed = self.leave_account(account.account_id)
            return self._payload("left", removed=removed)

    def _position(self, account_id: int) -> int:
        return next((index for index, request in enumerate(self.queue.snapshot(), 1)
                     if request.account_id == account_id), 0)
