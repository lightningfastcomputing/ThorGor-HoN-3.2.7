from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from enum import Enum


class ServerState(str, Enum):
    SLEEPING = "sleeping"
    IDLE = "idle"
    ALLOCATED = "allocated"
    IN_MATCH = "in_match"
    OFFLINE = "offline"


@dataclass(frozen=True)
class DedicatedServer:
    server_id: str
    host: str
    port: int
    state: ServerState = ServerState.OFFLINE
    match_id: int | None = None


class ServerRegistry:
    def __init__(self) -> None:
        self._servers: dict[str, DedicatedServer] = {}
        self._lock = threading.RLock()

    def register(self, server: DedicatedServer) -> DedicatedServer:
        with self._lock:
            self._servers[server.server_id] = server
            return server

    def update(self, server_id: str, *, state: ServerState, match_id: int | None = None) -> DedicatedServer:
        with self._lock:
            current = self._servers[server_id]
            updated = replace(current, state=state, match_id=match_id)
            self._servers[server_id] = updated
            return updated

    def allocate(self, match_id: int) -> DedicatedServer | None:
        with self._lock:
            available = sorted(
                (s for s in self._servers.values() if s.state is ServerState.IDLE),
                key=lambda s: s.server_id,
            )
            if not available:
                return None
            chosen = replace(available[0], state=ServerState.ALLOCATED, match_id=match_id)
            self._servers[chosen.server_id] = chosen
            return chosen

    def snapshot(self) -> tuple[DedicatedServer, ...]:
        with self._lock:
            return tuple(sorted(self._servers.values(), key=lambda s: s.server_id))

