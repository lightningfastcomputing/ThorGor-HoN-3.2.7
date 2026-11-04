"""Authenticated completion of exactly the current native match."""
import hmac


def completion_updates(state, session, match_id):
    expected = str(state.get("server_session") or state.get("manager_session") or "")
    if not session or not expected or not hmac.compare_digest(session, expected):
        raise ValueError("Invalid server session")
    if match_id <= 0:
        raise ValueError("Invalid completed match ID")
    current = int(state.get("match_id") or 0)
    if current == 0 and int(state.get("last_completed_match_id") or 0) == match_id:
        return {}
    if current != match_id:
        raise ValueError("Completed match is not the current match")
    return {"last_completed_match_id": match_id, "match_id": 0,
            "lifecycle": "idle", "match_host_key": "", "match_host_account_id": 0,
            "match_host_nickname": "", "match_name": "", "match_map": "",
            "match_date": "", "match_options": "", "pending_host_key": "",
            "pending_host_account_id": 0, "pending_host_nickname": "",
            "pending_host_reserved_at": 0.0, "native_start_game_injected": False,
            "native_completion_source": "ended_then_context_cleared"}
