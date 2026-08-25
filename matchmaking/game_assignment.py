from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameAssignment:
    match_id: int
    mode: str
    server_id: str
    host: str
    port: int
    account_ids: tuple[int, ...]

