"""Public CREATE/JOIN server-list policy."""
from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Callable
from typing import Any

from .auth import CHAT_SERVER_AUTHENTICATION_SALT


class ServerListService:
    def __init__(self, config: object, read_state: Callable[[], dict[str, Any]],
                 update_state: Callable[..., dict[str, Any]], ready: Callable[[], bool],
                 logger: Callable[[str], None]) -> None:
        self.config = config
        self.read_state = read_state
        self.update_state = update_state
        self.ready = ready
        self.log = logger

    def response(self, cookie: str, game_type: str) -> dict[Any, Any]:
        account_key = str(uuid.uuid4())
        account_key_hash = hashlib.sha1(
            (account_key + cookie + CHAT_SERVER_AUTHENTICATION_SALT).encode("utf-8")
        ).hexdigest()
        state = self.read_state()
        ready = self.ready()
        pending_key = str(state.get("pending_host_key") or "")
        try:
            reservation_age = time.time() - float(state.get("pending_host_reserved_at", 0.0))
        except (TypeError, ValueError):
            reservation_age = float("inf")
        reserved = bool(pending_key) and 0 <= reservation_age < 60
        if pending_key and not reserved:
            state = self.update_state(
                pending_host_key="", pending_host_account_id=0, pending_host_nickname="",
                pending_host_reserved_at=0.0,
                lifecycle="idle" if not state.get("match_id") else state.get("lifecycle", "lobby"),
            )
        try:
            lobby_active = int(state.get("match_id", 0)) > 0
        except (TypeError, ValueError):
            lobby_active = False
        picker_ip = self.config.server_list_ip or self.config.match_server_ip
        picker_port = self.config.server_list_port
        servers: dict[int, dict[str, str]] = {}
        if game_type == "90" and picker_ip and ready and not lobby_active and not reserved:
            servers[self.config.match_server_id] = {
                "server_id": str(self.config.match_server_id), "ip": picker_ip,
                "port": str(picker_port), "location": self.config.match_server_location,
                "c_state": "1",
            }
            self.log(f"PUBLIC_PICKER_ROW gametype=90 server_id={self.config.match_server_id} "
                     f"advertised={picker_ip}:{picker_port} real_slave={self.config.match_server_ip}:"
                     f"{self.config.match_server_port} status={state.get('server_status')}")
        elif game_type == "90":
            self.log(f"PUBLIC_PICKER_EMPTY gametype=90 ready={ready} reserved={reserved} "
                     f"lobby_active={lobby_active} match_id={state.get('match_id')}")
        if game_type == "10" and picker_ip and ready and lobby_active:
            servers[self.config.match_server_id] = {
                "server_id": str(self.config.match_server_id), "ip": picker_ip,
                "port": str(picker_port), "location": self.config.match_server_location,
                "class": "1",
            }
            self.log(f"PUBLIC_JOIN_ROW gametype=10 server_id={self.config.match_server_id} "
                     f"advertised={picker_ip}:{picker_port} match_id={state.get('match_id')}")
        elif game_type == "10":
            self.log(f"PUBLIC_JOIN_EMPTY gametype=10 ready={ready} lobby_active={lobby_active} "
                     f"match_id={state.get('match_id')}")
        response: dict[Any, Any] = {"server_list": servers, "vested_threshold": 5, 0: True}
        if game_type == "90":
            response.update(acc_key=account_key, acc_key_hash=account_key_hash)
        return response
