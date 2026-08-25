from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .game_assignment import GameAssignment
from .matchmaker import Matchmaker
from .queue import MatchQueue, MatchRequest


class ClientProtocolStatus(str, Enum):
    NOT_REVERSED = "not_reversed"
    MASTER_ENDPOINT = "master_endpoint"
    CHAT_PROTOCOL_47 = "chat_protocol_47"


@dataclass(frozen=True)
class MatchmakingStatus:
    domain_logic: str
    simulation_api: bool
    live_client_protocol: ClientProtocolStatus
    detail: str


class MatchmakingService:
    """Application boundary for the queue shared by HTTP and chat adapters."""

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
            live_client_protocol=ClientProtocolStatus.CHAT_PROTOCOL_47,
            detail=(
                "HoN 3.2.7 chat protocol 47 group, loading, queue, assignment, and "
                "auto-connect messages allocate the proven dedicated slave."
            ),
        )


def isolated_queue() -> MatchQueue:
    """Return an empty queue for tools/tests without implying live protocol wiring."""
    return MatchQueue()
