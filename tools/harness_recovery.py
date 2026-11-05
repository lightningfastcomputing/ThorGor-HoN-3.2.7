"""Protocol reconnect with retained native identity and snapshot resynchronization."""
from __future__ import annotations

from thorgor.tools.harness_gameplay import (
    client_evidence, creator_departure, inspect_gameplay, observe_state,
    verify_baseline, wait_state,
)


def retained_identity(state, account_id):
    player = next(p for p in state["players"] if p["account_id_low30"] == account_id)
    return (state["native_match_id"], player["player"], player["team"],
            player["hero_index"], player["selected_hero"])


def selection_recovery(pid, clients, role, factory, transport, check, event):
    indices = (1, 0) if role == "both" else ((0,) if role == "creator" else (1,))
    for index in indices:
        name = "creator" if index == 0 else "joiner"
        account_id = clients[index].account_id
        before = inspect_gameplay(pid)
        original = next(p for p in before["players"] if p["account_id_low30"] == account_id)
        if before["phase"] not in (2, 3):
            raise RuntimeError("hero-selection recovery requires selection phase")
        clients[index].disconnect()
        departed = check(f"selection_{name}_departure", lambda: wait_state(
            pid, [clients[1-index]], lambda state: not any(
                p["account_id_low30"] == account_id and not p["connection_status"] & 1
                for p in state["players"]), "selection_player_departed", event, timeout=5))
        event("hero_selection_departure", role=name, before=before, after=departed,
              native_transport=transport.inspect())
        replacement = factory(index)
        check(f"selection_{name}_bootstrap", lambda: replacement.admit([clients[1-index]]))
        replacement.finish_loading()
        after = check(f"selection_{name}_reentry", lambda: wait_state(
            pid, clients, lambda state: any(p["account_id_low30"] == account_id and
                not p["connection_status"] & 1 and
                p["native_client_number"] == replacement.native_number for p in state["players"])
                and replacement.snapshot_frames >= 3,
            "selection_player_reentered", event, timeout=15))
        returned = next(p for p in after["players"] if p["account_id_low30"] == account_id)
        event("hero_selection_reentry", role=name, before=original, after=returned,
              state=after, native_transport=transport.inspect())
        if (after["native_match_id"] != before["native_match_id"] or
                after["phase"] not in (2, 3) or
                retained_identity(after, account_id) != retained_identity(before, account_id)):
            raise RuntimeError("selection reconnect changed retained player, hero, team, phase, or match")


def recovery_cycle(pid, clients, role, factory, transport, job, check, event):
    indices = (1, 0) if role == "both" else ((0,) if role == "creator" else (1,))
    for index in indices:
        name, remaining = ("creator", "joiner") if index == 0 else ("joiner", "creator")
        before = inspect_gameplay(pid)
        previous = clients[index]
        account_id = previous.account_id
        old_frame = previous.last_snapshot_frame
        old_endpoint = previous.socket.getsockname()
        identity = retained_identity(before, account_id)
        check(f"{name}_departure", lambda: creator_departure(
            pid, [clients[index], clients[1-index]], job, check, event, transport=transport,
            departing_name=name, remaining_name=remaining))
        replacement = factory(index)
        check(f"{name}_reconnect_bootstrap", lambda: replacement.admit([clients[1-index]]))
        replacement.finish_loading()

        def resumed(state):
            player = next(p for p in state["players"] if p["account_id_low30"] == account_id)
            if player["connection_status"] & 1:
                return False
            return any(p["account_id_low30"] == account_id and p["state"] == 4 and
                       p["native_client_number"] == player["native_client_number"]
                       for p in transport.inspect()["clients"])

        after = check(f"{name}_reconnect_native", lambda: wait_state(
            pid, clients, resumed, f"{name}_reconnected", event, timeout=30))
        if retained_identity(after, account_id) != identity:
            raise RuntimeError("reconnect changed retained player, team, hero, or match")
        if replacement.socket.getsockname() == old_endpoint:
            raise RuntimeError("reconnect reused the retired downstream endpoint")
        event("reconnect_native_identity", role=name, account_id=account_id, before=before,
              after=after, native_transport=transport.inspect(), client=client_evidence(replacement))
        check(f"{name}_reconnect_resynchronization", lambda: wait_state(
            pid, clients, lambda state: state["phase"] == 6 and
            replacement.snapshot_frames >= 8 and replacement.last_snapshot_frame is not None and
            old_frame is not None and 0 < (replacement.last_snapshot_frame-old_frame) & 0xFFFFFFFF < 0x80000000,
            f"{name}_snapshot_resynchronization", event, timeout=30))
        samples = check(f"{name}_reconnect_snapshots", lambda: observe_state(
            pid, clients, job, f"after_{name}_reconnect", event, transport=transport))
        check(f"{name}_reconnect_both_streams", lambda: verify_baseline(samples))
        frame = replacement.last_snapshot_frame
        if old_frame is None or frame is None or not 0 < (frame-old_frame) & 0xFFFFFFFF < 0x80000000:
            raise RuntimeError("reconnected snapshot stream did not advance beyond departure")
        event("reconnect_result", role=name, account_id=account_id,
              previous_frame=old_frame, resynchronized_frame=frame,
              native_state=inspect_gameplay(pid), native_transport=transport.inspect())
