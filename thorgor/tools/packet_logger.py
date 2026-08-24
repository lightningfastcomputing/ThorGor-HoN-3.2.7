from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class PacketLogger:
    """Append-only JSONL packet evidence with explicit protocol and direction."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, protocol: str, direction: str, payload: bytes, **context) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "protocol": protocol,
            "direction": direction,
            "payload_hex": payload.hex(),
            **context,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

