"""Typed ownership of per-client UDP routes."""
from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field

from .packet_decoding import ConnectC0


@dataclass(slots=True)
class ClientRoute:
    client: tuple[str, int]
    upstream: socket.socket
    source_ip: str
    connected: ConnectC0 | None = None
    last_activity: float = field(default_factory=time.time)
    counters: dict[str, int] = field(default_factory=dict)


class RouteTable:
    def __init__(self, maximum: int) -> None:
        self.maximum = maximum
        self._routes: dict[tuple[str, int], ClientRoute] = {}

    def add(self, route: ClientRoute) -> None:
        if route.client not in self._routes and len(self._routes) >= self.maximum:
            raise RuntimeError("maximum client routes reached")
        self._routes[route.client] = route

    def get(self, client: tuple[str, int]) -> ClientRoute | None:
        return self._routes.get(client)

    def remove(self, client: tuple[str, int]) -> ClientRoute | None:
        return self._routes.pop(client, None)

    def snapshot(self) -> tuple[ClientRoute, ...]:
        return tuple(self._routes.values())
