"""Creator decisions for authenticated game connections."""
from __future__ import annotations

import hmac
import threading


RESERVATION_LOCK = threading.RLock()


def classify_match_host(account_id: int, host_key: str, state: dict) -> tuple[bool, bool]:
    """Return (creator, reserve). An active/pending owner cannot be displaced.

    The idle CREATE flow establishes its reservation at the first authenticated
    C0 carrying a key, as in the original ThorGor public-game workflow.
    """
    try:
        match_id = int(state.get("match_id") or 0)
        owner = int(state.get("match_host_account_id") or 0)
        pending_owner = int(state.get("pending_host_account_id") or 0)
    except (ValueError, TypeError):
        return False, False
    if account_id <= 0 or not host_key:
        return False, False

    def matches(value):
        return bool(value) and hmac.compare_digest(
            host_key.encode("utf-8"), str(value).encode("utf-8")
        )

    if match_id > 0:
        return account_id == owner and matches(state.get("match_host_key")), False
    if state.get("pending_host_key"):
        return account_id == pending_owner and matches(state["pending_host_key"]), False
    return True, True
