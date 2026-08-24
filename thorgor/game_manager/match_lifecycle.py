from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class MatchPhase(str, Enum):
    CREATED = "created"
    ALLOCATED = "allocated"
    LOBBY = "lobby"
    PLAYING = "playing"
    COMPLETE = "complete"
    FAILED = "failed"


_ALLOWED = {
    MatchPhase.CREATED: {MatchPhase.ALLOCATED, MatchPhase.FAILED},
    MatchPhase.ALLOCATED: {MatchPhase.LOBBY, MatchPhase.FAILED},
    MatchPhase.LOBBY: {MatchPhase.PLAYING, MatchPhase.FAILED},
    MatchPhase.PLAYING: {MatchPhase.COMPLETE, MatchPhase.FAILED},
    MatchPhase.COMPLETE: set(),
    MatchPhase.FAILED: set(),
}


@dataclass(frozen=True)
class MatchLifecycle:
    match_id: int
    phase: MatchPhase = MatchPhase.CREATED

    def transition(self, phase: MatchPhase) -> "MatchLifecycle":
        if phase not in _ALLOWED[self.phase]:
            raise ValueError(f"invalid match transition: {self.phase.value} -> {phase.value}")
        return replace(self, phase=phase)

