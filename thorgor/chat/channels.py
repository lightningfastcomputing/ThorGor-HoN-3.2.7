from __future__ import annotations

import threading
from collections import defaultdict


class ChannelDirectory:
    """Thread-safe channel membership, independent of socket handling."""

    def __init__(self) -> None:
        self._members: dict[str, set[str]] = defaultdict(set)
        self._lock = threading.RLock()

    def join(self, channel: str, nickname: str) -> tuple[str, ...]:
        with self._lock:
            self._members[channel.casefold()].add(nickname)
            return tuple(sorted(self._members[channel.casefold()], key=str.casefold))

    def leave(self, channel: str, nickname: str) -> tuple[str, ...]:
        with self._lock:
            key = channel.casefold()
            self._members[key].discard(nickname)
            remaining = tuple(sorted(self._members[key], key=str.casefold))
            if not remaining:
                self._members.pop(key, None)
            return remaining

    def members(self, channel: str) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._members.get(channel.casefold(), ()), key=str.casefold))

