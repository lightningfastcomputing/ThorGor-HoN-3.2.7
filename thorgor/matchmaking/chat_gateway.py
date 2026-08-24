"""Live HoN chat-protocol adapter for the LAN matchmaking endpoint."""
from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from thorgor.protocols import matchmaking_protocol as wire

from .endpoint import MatchmakingEndpoint
from .game_assignment import GameAssignment

Sender = Callable[[int, bytes], None]
StateReader = Callable[[], dict[str, object]]
Logger = Callable[[str], None]


@dataclass(slots=True)
class Session:
    nickname: str
    send: Sender


class MatchmakingChatGateway:
    """Translate protocol-47 TMM commands into queue and allocation operations."""

    def __init__(self, endpoint: MatchmakingEndpoint, read_state: StateReader,
                 *, logger: Logger = lambda _message: None) -> None:
        self.endpoint = endpoint
        self.read_state = read_state
        self.logger = logger
        self.sessions: dict[int, Session] = {}
        self.groups: dict[int, wire.GroupState] = {}
        self._brokers: set[tuple[str, int]] = set()
        self._notified_matches: set[int] = set()
        self._lock = threading.RLock()

    def bind(self, account_id: int, nickname: str, send: Sender) -> None:
        with self._lock:
            self.sessions[account_id] = Session(nickname, send)

    def unbind(self, account_id: int, send: Sender) -> None:
        with self._lock:
            current = self.sessions.get(account_id)
            if current is not None and current.send == send:
                self.sessions.pop(account_id, None)
                self.groups.pop(account_id, None)
                self.endpoint.leave_account(account_id)

    def handles(self, command: int) -> bool:
        return command in {
            wire.TMM_GROUP_CREATE, wire.TMM_GROUP_LEAVE,
            wire.TMM_GROUP_LEAVE_QUEUE, wire.TMM_PLAYER_LOADING,
            wire.TMM_PLAYER_READY, wire.TMM_POPULARITY,
        }

    def process(self, account_id: int, command: int, payload: bytes) -> None:
        if command == wire.TMM_GROUP_CREATE:
            self._create(account_id, payload)
        elif command == wire.TMM_PLAYER_READY:
            self._ready(account_id, payload)
        elif command == wire.TMM_PLAYER_LOADING:
            self._loading(account_id, payload)
        elif command in {wire.TMM_GROUP_LEAVE, wire.TMM_GROUP_LEAVE_QUEUE}:
            self.endpoint.leave_account(account_id)
            with self._lock:
                self.groups.pop(account_id, None)
            self._send(account_id, wire.TMM_LEFT_QUEUE)
        elif command == wire.TMM_POPULARITY:
            # The stock panel tolerates an absent popularity update. Its
            # availability gate is supplied by the deterministic UI overlay.
            self.logger(f"TMM_POPULARITY account_id={account_id}")

    def _create(self, account_id: int, payload: bytes) -> None:
        request = wire.GroupRequest.decode(payload)
        with self._lock:
            session = self.sessions.get(account_id)
            if session is None:
                raise ValueError("TMM group creation requires an authenticated chat session")
            group = wire.GroupState(account_id, session.nickname, request)
            self.groups[account_id] = group
        self.endpoint.reset_account(account_id)
        self._send(account_id, wire.TMM_GROUP_UPDATE, wire.group_update(group, 0))
        self.logger(
            f"TMM_GROUP_CREATED account_id={account_id} type={request.group_type} "
            f"game_type={request.game_type} map={request.map_name!r} "
            f"modes={request.game_modes!r} regions={request.regions!r}"
        )

    def _ready(self, account_id: int, payload: bytes) -> None:
        group = self._group(account_id)
        group.ready = bool(payload[0]) if payload else True
        if len(payload) >= 2:
            group.request = replace(group.request, game_type=payload[1])
        self._send(account_id, wire.TMM_GROUP_UPDATE, wire.group_update(group, 2))
        if group.ready:
            self._send(account_id, wire.TMM_START_LOADING)
        self.logger(f"TMM_READY account_id={account_id} ready={group.ready}")

    def _loading(self, account_id: int, payload: bytes) -> None:
        group = self._group(account_id)
        group.loading_percent = min(100, payload[0] if payload else 0)
        self._send(account_id, wire.TMM_GROUP_UPDATE, wire.group_update(group, 2))
        if group.loading_percent < 100:
            return
        players = 1 if group.request.is_coop else 2
        result = self.endpoint.join_account(
            account_id, group.nickname, group.request.queue_mode,
            players_per_match=players,
        )
        self._send(account_id, wire.TMM_ENTERED_QUEUE)
        self._send(account_id, wire.TMM_QUEUE_UPDATE, wire.queue_time(0))
        self.logger(
            f"TMM_QUEUED account_id={account_id} mode={group.request.queue_mode!r} "
            f"players={players} status={result['status']!r}"
        )
        assignment = self.endpoint.assignment_for(account_id)
        if assignment is not None:
            self._notify_assignment(assignment)
        else:
            self._start_broker(group.request.queue_mode, players)

    def _start_broker(self, mode: str, players: int) -> None:
        key = (mode, players)
        with self._lock:
            if key in self._brokers:
                return
            self._brokers.add(key)
        threading.Thread(target=self._broker, args=key, daemon=True,
                         name=f"tmm-{mode}-{players}").start()

    def _broker(self, mode: str, players: int) -> None:
        try:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                assignment = self.endpoint.try_assign(mode, players)
                if assignment is not None:
                    self._notify_assignment(assignment)
                    return
                time.sleep(0.5)
        finally:
            with self._lock:
                self._brokers.discard((mode, players))

    def _notify_assignment(self, assignment: GameAssignment) -> None:
        with self._lock:
            if assignment.match_id in self._notified_matches:
                return
            self._notified_matches.add(assignment.match_id)
        for account_id in assignment.account_ids:
            group = self.groups.get(account_id)
            if group is None:
                continue
            self._send(account_id, wire.TMM_LEFT_QUEUE)
            self._send(account_id, wire.TMM_MATCH_FOUND,
                       wire.match_found(group, assignment.match_id))
            self._send(account_id, wire.TMM_QUEUE_UPDATE,
                       bytes((wire.TMM_UPDATE_FOUND_SERVER,)))
        self.logger(
            f"TMM_MATCH_ASSIGNED match_id={assignment.match_id} accounts={assignment.account_ids!r} "
            f"server={assignment.host}:{assignment.port}"
        )
        threading.Thread(target=self._connect_when_ready, args=(assignment,), daemon=True,
                         name=f"tmm-connect-{assignment.match_id}").start()

    def _connect_when_ready(self, assignment: GameAssignment) -> None:
        deadline = time.monotonic() + 15
        ready = False
        while time.monotonic() < deadline:
            state = self.read_state()
            try:
                injected_for = int(state.get("native_start_game_injected_for", 0) or 0)
            except (TypeError, ValueError):
                injected_for = 0
            if injected_for == assignment.match_id:
                ready = True
                break
            time.sleep(0.25)
        if not ready:
            self.logger(f"TMM_CONNECT_TIMEOUT match_id={assignment.match_id}")
            return
        nonce = secrets.randbits(31)
        for account_id in assignment.account_ids:
            group = self.groups.get(account_id)
            if group is None:
                continue
            group.in_game = True
            self._send(
                account_id, wire.AUTO_MATCH_CONNECT,
                wire.auto_match_connect(group, assignment.match_id,
                                        assignment.host, assignment.port, nonce),
            )
        self.logger(
            f"TMM_AUTO_CONNECT match_id={assignment.match_id} accounts={assignment.account_ids!r} "
            f"server={assignment.host}:{assignment.port}"
        )

    def _group(self, account_id: int) -> wire.GroupState:
        with self._lock:
            group = self.groups.get(account_id)
        if group is None:
            raise ValueError(f"account {account_id} has no matchmaking group")
        return group

    def _send(self, account_id: int, command: int, payload: bytes = b"") -> None:
        with self._lock:
            session = self.sessions.get(account_id)
        if session is None:
            return
        try:
            session.send(command, payload)
        except OSError as exc:
            self.logger(f"TMM_SEND_ERROR account_id={account_id} command=0x{command:04X} error={exc!r}")
