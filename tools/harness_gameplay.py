"""Native gameplay controls and read-only acceptance evidence."""
from __future__ import annotations

import struct
import time

from thorgor.game_manager.native_match_id import (
    RemoteProcess, inspect_native_match_id, inspect_native_players, module_info,
)
from thorgor.patches.installer import file_hash


GAME_SHARED_SHA256 = "37BBC4706D06AE9857F2C56FDECE0E53F0E656A12ECDA6556CAE546CEC73506F"
PHASES = {0: "idle", 1: "waiting", 2: "hero_select", 3: "hero_lock",
          4: "hero_loading", 5: "pre_match", 6: "active", 7: "ended"}


def verify_gameplay_module(pid):
    module = module_info(pid, "game_shared.dll")
    if module is None or file_hash(module[1]) != GAME_SHARED_SHA256:
        raise ValueError("gameplay inspector requires the audited game_shared.dll")


def inspect_gameplay(pid):
    info = inspect_native_match_id(pid)
    players = inspect_native_players(pid, info["cgame"])
    with RemoteProcess(pid) as process:
        phase = process.read_u32(info["cgameinfo"] + 0x78)
        clock = process.read_u32(info["cgame"] + 4)
        phase_duration = process.read_u32(info["cgameinfo"] + 0x80)
        for player in players:
            address = int(player["player"], 16)
            player["team"] = process.read_u32(address + 0x70)
            player["hero_index"] = process.read_u32(address + 0x74)
            player["selected_hero"] = process.read_u32(address + 0x84) & 0xFFFF
    return {"phase": phase, "phase_name": PHASES.get(phase, "unknown"),
            "engine_time": clock, "phase_duration": phase_duration,
            "native_match_id": info["native_match_id"],
            "players": players}


def client_evidence(client):
    return {"account_id": client.account_id, "native_number": client.native_number,
            "endpoint": list(client.socket.getsockname()),
            "sent": client.sent, "received": client.received,
            "unique_reliable": client.unique_reliable,
            "snapshot_frames": client.snapshot_frames, "last_snapshot_frame": client.last_snapshot_frame,
            "snapshot_errors": client.snapshot_errors, "snapshot_packets": client.snapshot_packets,
            "snapshot_complete": client.snapshot_complete,
            "packet_types": dict(client.packet_types),
            "packet_shapes": [{"kind": kind, "bytes": size, "header": header}
                              for (kind, size), header in client.packet_shapes.items()]}


def wait_state(pid, clients, predicate, label, event, timeout=30):
    deadline = time.monotonic() + timeout
    signature = None
    while time.monotonic() < deadline:
        for client in clients:
            client.poll()
        state = inspect_gameplay(pid)
        current = (state["phase"], tuple((p["team"], p["selected_hero"], p["hero_index"])
                                        for p in state["players"]))
        if current != signature:
            event("gameplay_native_state", step=label, state=state)
            signature = current
        if predicate(state):
            return state
        time.sleep(0.03)
    event("gameplay_timeout", step=label, state=state,
          clients=[client_evidence(client) for client in clients])
    raise TimeoutError(f"native gameplay did not reach {label}")


def start_gameplay(pid, clients, check, event):
    check("verify_gameplay_inspector", lambda: verify_gameplay_module(pid))
    event("gameplay_initial_state", state=inspect_gameplay(pid))
    for client in clients:
        client.finish_loading()
    for team, client in enumerate(clients, start=1):
        client.game_command(0x01, struct.pack("<II", team, 0))
    check("native_teams", lambda: wait_state(
        pid, clients, lambda state: {p["team"] for p in state["players"]} == {1, 2},
        "teams", event,
    ))
    for client in clients:
        client.game_command(0x2F)
    clients[0].game_command(0x30)
    check("native_hero_selection_phase", lambda: wait_state(
        pid, clients, lambda state: state["phase"] in (2, 3),
        "hero_selection", event, timeout=30,
    ))
    for client in clients:
        client.game_command(0x07)
    check("native_heroes_selected", lambda: wait_state(
        pid, clients, lambda state: len(state["players"]) == 2 and
        all(p["selected_hero"] != 0xFFFF for p in state["players"]),
        "heroes_selected", event,
    ))
    for client in clients:
        client.game_command(0x2F)
    check("native_hero_loading", lambda: wait_state(
        pid, clients, lambda state: state["phase"] in (4, 5, 6),
        "hero_loading", event,
    ))
    for client in clients:
        client.finish_loading()
    return check("native_active_gameplay", lambda: wait_state(
        pid, clients, lambda state: state["phase"] == 6 and len(state["players"]) == 2 and
        all(p["hero_index"] != 0xFFFFFFFF for p in state["players"]),
        "active_gameplay", event, timeout=150,
    ))


def observe_state(pid, clients, job, label, event, seconds=5, transport=None):
    samples = []
    before = [client_evidence(client) for client in clients]
    first_clock = inspect_gameplay(pid)["engine_time"]
    for number in range(seconds):
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            for client in clients:
                client.poll()
        state = inspect_gameplay(pid)
        if pid not in job.pids() or state["phase"] != 6:
            raise RuntimeError("authoritative active server did not survive observation")
        current = [client_evidence(client) for client in clients]
        sample = {"second": number + 1, "engine_time": state["engine_time"],
                  "pid": pid, "native_state": state,
                  "native_transport": transport.inspect() if transport else None,
                  "clients": [{
                      "account_id": now["account_id"], "native_number": now["native_number"],
                      "snapshot_frames": now["snapshot_frames"] - old["snapshot_frames"],
                      "received": now["received"] - old["received"],
                      "sent": now["sent"] - old["sent"],
                      "snapshot_errors": now["snapshot_errors"] - old["snapshot_errors"],
                      "snapshot_packets": now["snapshot_packets"] - old["snapshot_packets"],
                      "snapshot_complete": now["snapshot_complete"] - old["snapshot_complete"],
                      "last_snapshot_frame": now["last_snapshot_frame"],
                  } for old, now in zip(before, current)]}
        samples.append(sample)
        event("gameplay_state_sample", window=label, sample=sample)
        before = current
    if not 0 < (state["engine_time"] - first_clock) & 0xFFFFFFFF < 0x80000000:
        raise RuntimeError("authoritative server clock stopped")
    return samples


def verify_baseline(samples):
    if len(samples) < 3 or not all(len(sample["clients"]) == 2 and
               all(client["snapshot_frames"] > 0 for client in sample["clients"])
               for sample in samples[-3:]):
        raise RuntimeError("both clients need ongoing complete snapshots before disconnection")


def creator_departure(pid, clients, job, check, event, transport=None, expect_freeze=False):
    creator, joiner = clients
    endpoint = joiner.socket.getsockname()
    before = inspect_gameplay(pid)
    before_transport = transport.inspect() if transport else None
    event("departure_expectation", expected="reproduced_freeze" if expect_freeze else "continued_state",
          required_seconds=15, native_state=before,
          native_transport=before_transport,
          clients=[client_evidence(client) for client in clients] if transport else [])
    joiner_number = next(p["native_client_number"] for p in before["players"]
                         if p["account_id_low30"] == joiner.account_id)
    creator.disconnect()
    event("creator_c3_sent", joiner_endpoint=list(endpoint))
    check("native_creator_disconnected", lambda: wait_state(
        pid, [joiner], lambda state: any(
            p["account_id_low30"] == creator.account_id and p["connection_status"] & 1
            for p in state["players"]), "creator_disconnected", event, timeout=5,
    ))
    samples = observe_state(pid, [joiner], job, "after_creator_departure", event,
                            seconds=15, transport=transport)
    if joiner.socket.getsockname() != endpoint:
        raise RuntimeError("joiner transport changed during observation")
    after = inspect_gameplay(pid)
    if not any(p["account_id_low30"] == joiner.account_id and
               p["native_client_number"] == joiner_number and
               not p["connection_status"] & 1
               for p in after["players"]):
        raise RuntimeError("joiner native connection changed")
    classification = classify_departure(samples)
    if classification == "continued_state" and not expect_freeze:
        check("joiner_15s_continuity", lambda: verify_continuity(
            samples, before, joiner.account_id, expected_transport=before_transport))
    event("creator_departure_result", classification=classification,
          expected="reproduced_freeze" if expect_freeze else "continued_state",
          observation_seconds=15, joiner_endpoint=list(endpoint), native_state=after)
    expected = "reproduced_freeze" if expect_freeze else "continued_state"
    if classification != expected:
        raise RuntimeError(f"creator-departure regression result {classification}")


def player_identity(state, account_id):
    player = next(p for p in state["players"] if p["account_id_low30"] == account_id)
    return (state["native_match_id"], player["player"], player["native_client_number"],
            player["team"], player["hero_index"], player["selected_hero"])


def verify_continuity(samples, before, account_id, seconds=15, expected_transport=None):
    if len(samples) < seconds:
        raise RuntimeError("continuity observation was too short")
    identity = player_identity(before, account_id)
    clock = before["engine_time"]
    first_transport = expected_transport or samples[0]["native_transport"]
    server = first_transport["server"] if first_transport else None
    endpoint, connection = None, None
    if first_transport:
        original = next(p for p in first_transport["clients"] if p["account_id_low30"] == account_id)
        endpoint, connection = original["endpoint"], original["connection"]
    for sample in samples:
        state = sample["native_state"]
        player = next(p for p in state["players"] if p["account_id_low30"] == account_id)
        if (state["phase"] != 6 or player_identity(state, account_id) != identity or
                player["connection_status"] & 1 or
                not 0 < (state["engine_time"] - clock) & 0xFFFFFFFF < 0x80000000):
            raise RuntimeError("native match or joiner identity/clock changed")
        clock = state["engine_time"]
        client = sample["clients"][0]
        if client["snapshot_frames"] <= 0 or client["snapshot_errors"] or client["sent"] <= 0:
            raise RuntimeError("joiner needs fresh authoritative state in every observation window")
        native = sample["native_transport"]
        if native:
            if native["server"] != server:
                raise RuntimeError("native server identity changed")
            record = next((p for p in native["clients"] if p["account_id_low30"] == account_id), None)
            if record is None or record["native_client_number"] != identity[2] or record["state"] != 4:
                raise RuntimeError("joiner left the native transport registry")
            if endpoint is None:
                endpoint, connection = record["endpoint"], record["connection"]
            if record["endpoint"] != endpoint or record["connection"] != connection:
                raise RuntimeError("joiner native endpoint or transport object changed")


def classify_departure(samples):
    tail = [sample["clients"][0] for sample in samples[-3:]]
    if len(tail) < 3 or any(sample["snapshot_errors"] for sample in tail):
        return "inconclusive"
    if all(sample["snapshot_frames"] > 0 for sample in tail):
        return "continued_state"
    if all(sample["snapshot_frames"] == 0 and sample["sent"] > 0 and
           (sample["snapshot_packets"] == 0 or sample["snapshot_complete"] > 0)
           for sample in tail):
        return "reproduced_freeze"
    return "inconclusive"
