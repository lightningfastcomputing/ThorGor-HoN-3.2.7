"""HoN 3.2.7 matchmaking messages carried by chat protocol 47."""
from __future__ import annotations

import struct
from dataclasses import dataclass

from thorgor.chat.protocol import cstr, read_cstr


# Client -> chat server.
TMM_GROUP_CREATE = 0x0C0A
TMM_GROUP_LEAVE = 0x0C0C
TMM_GROUP_LEAVE_QUEUE = 0x0D02
TMM_PLAYER_LOADING = 0x0D04
TMM_PLAYER_READY = 0x0D05
TMM_POPULARITY = 0x0D07

# Chat server -> client. Several command IDs are intentionally bidirectional.
TMM_ENTERED_QUEUE = 0x0D01
TMM_LEFT_QUEUE = 0x0D02
TMM_GROUP_UPDATE = 0x0D03
TMM_QUEUE_UPDATE = 0x0D06
TMM_MATCH_FOUND = 0x0D09
TMM_START_LOADING = 0x0F03
AUTO_MATCH_CONNECT = 0x0062

TMM_UPDATE_QUEUE_TIME = 11
TMM_UPDATE_FOUND_SERVER = 16


@dataclass(frozen=True, slots=True)
class GroupRequest:
    version: str
    group_type: int
    game_type: int
    map_name: str
    game_modes: tuple[str, ...]
    regions: tuple[str, ...]
    ranked: bool
    fidelity: int
    bot_difficulty: int
    randomize_bots: bool

    @classmethod
    def decode(cls, payload: bytes) -> "GroupRequest":
        offset = 0
        version, offset = read_cstr(payload, offset)
        if len(payload) < offset + 2:
            raise ValueError("TMM group-create payload is missing type fields")
        group_type, game_type = payload[offset], payload[offset + 1]
        offset += 2
        map_name, offset = read_cstr(payload, offset)
        modes, offset = read_cstr(payload, offset)
        regions, offset = read_cstr(payload, offset)
        if len(payload) < offset + 4:
            raise ValueError("TMM group-create payload is missing option fields")
        ranked, fidelity, bot_difficulty, randomize_bots = payload[offset:offset + 4]
        return cls(
            version=version,
            group_type=group_type,
            game_type=game_type,
            map_name=map_name or "caldavar",
            game_modes=tuple(filter(None, modes.split("|"))) or ("ap",),
            regions=tuple(filter(None, regions.split("|"))) or ("USE",),
            ranked=bool(ranked),
            fidelity=fidelity,
            bot_difficulty=bot_difficulty,
            randomize_bots=bool(randomize_bots),
        )

    @property
    def is_coop(self) -> bool:
        return self.group_type == 3

    @property
    def queue_mode(self) -> str:
        return "botmatch" if self.is_coop else "allpick"

    @property
    def arranged_match_type(self) -> int:
        if self.is_coop:
            return 5
        if self.game_type == 3:
            return 4
        if self.game_type == 4:
            return 7
        return 1 if self.ranked else 6


@dataclass(slots=True)
class GroupState:
    account_id: int
    nickname: str
    request: GroupRequest
    ready: bool = False
    loading_percent: int = 0
    in_game: bool = False


def _header(group: GroupState, update_type: int) -> bytearray:
    request = group.request
    data = bytearray()
    data += struct.pack("<BIBhIBB", update_type, group.account_id, 1, 1500,
                        group.account_id, request.arranged_match_type, request.game_type)
    data += cstr(request.map_name)
    data += cstr("|".join(request.game_modes))
    data += cstr("|".join(request.regions))
    data += bytes((int(request.ranked), request.fidelity, request.bot_difficulty,
                   int(request.randomize_bots)))
    data += cstr("") + cstr("")
    data += bytes((5, request.group_type))
    return data


def group_update(group: GroupState, update_type: int) -> bytes:
    """Encode a one-player group update; type 0 is the complete snapshot."""
    data = _header(group, update_type)
    full = update_type in {0, 1, 3, 4, 5}
    if full:
        data += struct.pack("<I", group.account_id)
        data += cstr(group.nickname)
        data += struct.pack("<BiiiiBh", 1, 0, 0, -1, -1, 1,
                            1500 if group.request.ranked else -1)
    data += bytes((group.loading_percent, int(group.ready), int(group.in_game)))
    if full:
        data += b"\x01" + cstr("") + cstr("") + cstr("US") + b"\x01"
        data += cstr("|".join("true" for _ in group.request.game_modes))
        data += b"\x00"  # recipient-specific friendship status
    return bytes(data)


def queue_time(seconds: int = 0) -> bytes:
    return struct.pack("<BI", TMM_UPDATE_QUEUE_TIME, max(0, seconds))


def match_found(group: GroupState, match_id: int) -> bytes:
    request = group.request
    mode = "botmatch" if request.is_coop else request.game_modes[0]
    team_size = 5 if request.is_coop else 1
    return (cstr(request.map_name) + bytes((team_size, request.game_type)) + cstr(mode)
            + cstr(request.regions[0]) + cstr(f"ThorGor Match #{match_id}"))


def auto_match_connect(group: GroupState, match_id: int, host: str, port: int,
                       nonce: int) -> bytes:
    return (bytes((group.request.arranged_match_type,)) + struct.pack("<I", match_id)
            + cstr(host) + struct.pack("<H", port) + struct.pack("<I", nonce & 0xFFFFFFFF))
