"""Protocol movement with read-only authoritative hero coordinates."""
from __future__ import annotations

import math
import struct

from thorgor.game_manager.native_match_id import (
    RemoteProcess, inspect_native_match_id, inspect_native_players,
)
from thorgor.tools.harness_gameplay import observe_state, verify_baseline, wait_state


def inspect_heroes(pid):
    info = inspect_native_match_id(pid)
    players = inspect_native_players(pid, info["cgame"])
    heroes = []
    with RemoteProcess(pid) as process:
        directory = process.read_u32(info["cgame"] + 0x20)
        begin, end = (process.read_u32(directory + offset) for offset in (0x10, 0x14))
        size = (end - begin) // 4
        if not begin or not 0 < size <= 0x100000:
            raise ValueError("invalid native entity vector")
        for player in players:
            address = int(player["player"], 16)
            index = process.read_u32(address + 0x74)
            selected_type = process.read_u32(address + 0x84) & 0xFFFF
            if not 0 <= index < size:
                raise ValueError("native hero index is outside the entity vector")
            entity = process.read_u32(begin + index * 4)
            if (process.read_u32(entity + 0x10) != index or
                    process.read_u32(entity + 0x38) & 0xFFFF != selected_type or
                    process.read_u32(entity + 0x444) != player["native_client_number"]):
                raise ValueError("native entity index/type/owner does not match its player")
            position = [struct.unpack("<f", struct.pack("<I", process.read_u32(entity + offset)))[0]
                        for offset in (0x98, 0x9C, 0xA0)]
            if not all(math.isfinite(value) and abs(value) < 1000000 for value in position):
                raise ValueError("invalid native hero coordinates")
            heroes.append({"account_id": player["account_id_low30"], "index": index,
                           "entity": f"0x{entity:08X}", "owner": player["native_client_number"],
                           "selected_type": selected_type, "position": position,
                           "selection_count": process.read_u32(address + 0x490)})
    return heroes


def order_position(index, x, y):
    # Actual 3.2.7.1 game.dll parser at C300: byte order, two floats,
    # uint32 parameter, byte queue, uint16 single entity, byte flags.
    if not 0 <= index < 0xFFFF or not all(math.isfinite(value) for value in (x, y)):
        raise ValueError("invalid movement target")
    return struct.pack("<BffIBHB", 2, x, y, 0, 0, index, 0)


def movement(pid, clients, job, transport, check, event):
    before = inspect_heroes(pid)
    event("movement_native_before", heroes=before)
    if any(hero["selection_count"] == 0 for hero in before):
        event("movement_blocked", reason="native_control_selection_missing",
              required="3.2.7.1 C7 player input entity snapshot containing control selection")
        raise RuntimeError("native player control selection has not been established")
    for client in clients:
        hero = next(p for p in before if p["account_id"] == client.account_id)
        x, y, _ = hero["position"]
        dx, dy = (256 if x < 8000 else -256), (128 if y < 8000 else -128)
        client.game_command(0x1E, order_position(hero["index"], x + dx, y + dy))

    def moved(state):
        if state["phase"] != 6:
            return False
        after = inspect_heroes(pid)
        return all(any(new["entity"] == old["entity"] and
                       math.dist(new["position"][:2], old["position"][:2]) > 32
                       for new in after) for old in before)

    check("both_heroes_move_authoritatively", lambda: wait_state(
        pid, clients, moved, "authoritative_hero_movement", event, timeout=12))
    event("movement_native_after", heroes=inspect_heroes(pid))
    samples = check("movement_state_streams", lambda: observe_state(
        pid, clients, job, "after_movement", event, transport=transport))
    check("movement_both_streams", lambda: verify_baseline(samples))
