from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .game_assignment import GameAssignment
from .matchmaker import Matchmaker
from .queue import MatchQueue, MatchRequest


class ClientProtocolStatus(str, Enum):
    NOT_REVERSED = "not_reversed"
    MASTER_ENDPOINT = "master_endpoint"


@dataclass(frozen=True)
class MatchmakingStatus:
    domain_logic: str
    simulation_api: bool
    live_client_protocol: ClientProtocolStatus
    detail: str


class MatchmakingService:
    """Application boundary for tested matchmaking logic, not a live HoN wire service."""

    def __init__(self, matchmaker: Matchmaker) -> None:
        self.matchmaker = matchmaker

    def queue(self, request: MatchRequest) -> bool:
        return self.matchmaker.queue.join(request)

    def leave(self, account_id: int) -> bool:
        return self.matchmaker.queue.leave(account_id)

    def form_simulated_match(self, mode: str = "allpick", players: int = 2) -> GameAssignment | None:
        return self.matchmaker.form_match(mode, players)

    @staticmethod
    def status() -> MatchmakingStatus:
        return MatchmakingStatus(
            domain_logic="implemented_and_tested",
            simulation_api=True,
            live_client_protocol=ClientProtocolStatus.MASTER_ENDPOINT,
            detail=(
                "Authenticated master queue/poll/leave operations allocate the proven idle "
                "dedicated slave. Native HoN 3.2.7 queue command IDs remain unverified."
            ),
        )


def isolated_queue() -> MatchQueue:
    """Return an empty queue for tools/tests without implying live protocol wiring."""
    return MatchQueue()
