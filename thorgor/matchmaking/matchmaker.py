from __future__ import annotations

import itertools
from collections.abc import Callable

from .game_assignment import GameAssignment
from .queue import MatchQueue


Allocator = Callable[[int, str, tuple[int, ...]], tuple[str, str, int]]


class Matchmaker:
    """Forms fixed-size FIFO LAN matches and delegates server allocation."""

    def __init__(self, queue: MatchQueue, allocator: Allocator, *, first_match_id: int = 1) -> None:
        self.queue = queue
        self.allocator = allocator
        self._match_ids = itertools.count(first_match_id)

    def form_match(self, mode: str = "allpick", players: int = 2) -> GameAssignment | None:
        requests = self.queue.take(players, mode)
        if not requests:
            return None
        match_id = next(self._match_ids)
        account_ids = tuple(request.account_id for request in requests)
        try:
            server_id, host, port = self.allocator(match_id, mode, account_ids)
        except Exception:
            self.queue.restore_front(requests)
            raise
        return GameAssignment(match_id, mode, server_id, host, port, account_ids)
