"""Reversible HoN resource overlay enabling the dormant matchmaking panel."""
from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

PATCH_ID = "client.matchmaking_ui_enable"
SOURCE_ARCHIVE = "resources0.s2z"
OVERLAY_ARCHIVE = "resources999.s2z"
MARKER_ENTRY = "thorgor/matchmaking_ui_patch.json"


@dataclass(frozen=True, slots=True)
class ResourceReplacement:
    entry: str
    source_sha256: str
    original: bytes
    replacement: bytes
    reason: str


PATCHES = (
    ResourceReplacement(
        "ui/scripts/main.lua",
        "0052D7F29F3E47313F4085C4505D5708D5C5949164D8474180663B045E5CB1FC",
        b"SetEnabled(IsTMMEnabled())",
        b"SetEnabled(true)",
        "Allow the main-menu Matchmaking button to receive clicks.",
    ),
    ResourceReplacement(
        "ui/fe2/main.interface",
        "61B46C17C99BF276DB521F7E851496FE7772E8AF2981B25FB0BE18C3FA82382B",
        b'ontrigger="SetVisible(!IsTMMEnabled());"',
        b'ontrigger="SetVisible(false);"',
        "Hide the transparent disabled-state click blocker.",
    ),
    ResourceReplacement(
        "ui/scripts/matchmaking.lua",
        "8EEE20A9D7FABE5D20682DED06A3AA7FECEF7E7A5C33FCA528D82BFDEC221497",
        b"if (not IsTMMEnabled()) then",
        b"if (false) then -- ThorGor local matchmaking availability",
        "Keep the matchmaking panel open while the retired availability service is absent.",
    ),
    ResourceReplacement(
        "ui/scripts/chat.lua",
        "23BEA7B8A49D064F19F470C3F42DEC7BF69EFE2DAB25D3D41D025DDB38EFB520",
        b"\tmessageType, channel, message, entity, premessage = messageType or '', channel or '', message or '', entity or '', ''\r\n",
        b"\tmessageType, channel, message, entity, premessage = messageType or '', channel or '', message or '', entity or '', ''\r\n"
        b"\tlocal thorgorTeamMarker = '[THORGOR_TEAM]'\r\n"
        b"\tif (string.find(message, thorgorTeamMarker, 1, true)) then\r\n"
        b"\t\tmessage = string.gsub(message, '%[THORGOR_TEAM%]', '', 1)\r\n"
        b"\t\tmessage = string.gsub(message, '%[ALL%]', '^y[TEAM]', 1)\r\n"
        b"\t\tmessageType = '5'\r\n"
        b"\tend\r\n",
        "Render private ThorGor chat mirrors with HoN's native player colors and team label.",
    ),
    ResourceReplacement(
        "ui/scripts/game_new.lua",
        "FDE9AFD0ACF335766104CA7C5FBE907F63C3A2ABFB5EC7FFE8F82741DF92B2FB",
        b"local function AllChatMessages(...)\r\n"
        b"\tif (GameChat) then\r\n"
        b"\t\tGameChat.AllChatMessages(...)\r\n"
        b"\tend\r\n"
        b"end\r\n",
        b"local function AllChatMessages(widget, messageType, channel, message, entity, noFormatting, isMe)\r\n"
        b"\tlocal thorgorTeamMarker = '[THORGOR_TEAM]'\r\n"
        b"\tif (message and string.find(message, thorgorTeamMarker, 1, true)) then\r\n"
        b"\t\tmessage = string.gsub(message, '%[THORGOR_TEAM%]', '', 1)\r\n"
        b"\t\tmessage = string.gsub(message, '%[ALL%]', '^y[TEAM]', 1)\r\n"
        b"\t\tmessageType = '5'\r\n"
        b"\tend\r\n"
        b"\tif (GameChat) then\r\n"
        b"\t\tGameChat.AllChatMessages(widget, messageType, channel, message, entity, noFormatting, isMe)\r\n"
        b"\tend\r\n"
        b"end\r\n",
        "Normalize ThorGor team-chat mirrors at the active game/picking watch boundary.",
    ),
    ResourceReplacement(
        "ui/scripts/specui.lua",
        "DBC1A39991D7CA9D56461013E1C0B43CE804FB4497C883C464E0B508E43945A8",
        b"local function AllChatMessages(...)\r\n"
        b"\tif (GameChat) then\r\n"
        b"\t\tGameChat.AllChatMessages(...)\r\n"
        b"\tend\r\n"
        b"end\r\n",
        b"local function AllChatMessages(widget, messageType, channel, message, entity, noFormatting, isMe)\r\n"
        b"\tlocal thorgorTeamMarker = '[THORGOR_TEAM]'\r\n"
        b"\tif (message and string.find(message, thorgorTeamMarker, 1, true)) then\r\n"
        b"\t\tmessage = string.gsub(message, '%[THORGOR_TEAM%]', '', 1)\r\n"
        b"\t\tmessage = string.gsub(message, '%[ALL%]', '^y[TEAM]', 1)\r\n"
        b"\t\tmessageType = '5'\r\n"
        b"\tend\r\n"
        b"\tif (GameChat) then\r\n"
        b"\t\tGameChat.AllChatMessages(widget, messageType, channel, message, entity, noFormatting, isMe)\r\n"
        b"\tend\r\n"
        b"end\r\n",
        "Normalize ThorGor team-chat mirrors at the spectator watch boundary.",
    ),
    ResourceReplacement(
        "ui/scripts/communicator.lua",
        "E74B9A6B271C876A7C87CE9F70A04C2F00C7101EFC6D03B024CD7827E34FE1AF",
        b"function HoN_Communicator:AllChatMessages(widget, msgType, channelName, text, entity, noFormatting, isSelf)\r\n"
        b"\tif (GameChat and UIGamePhase() > 0 and UIGamePhase() <= 4) then\r\n",
        b"function HoN_Communicator:AllChatMessages(widget, msgType, channelName, text, entity, noFormatting, isSelf)\r\n"
        b"\tlocal thorgorTeamMarker = '[THORGOR_TEAM]'\r\n"
        b"\tif (text and string.find(text, thorgorTeamMarker, 1, true)) then\r\n"
        b"\t\ttext = string.gsub(text, '%[THORGOR_TEAM%]', '', 1)\r\n"
        b"\t\ttext = string.gsub(text, '%[ALL%]', '^y[TEAM]', 1)\r\n"
        b"\t\tmsgType = '5'\r\n"
        b"\tend\r\n"
        b"\tif (GameChat and UIGamePhase() > 0 and UIGamePhase() <= 4) then\r\n",
        "Normalize ThorGor team-chat mirrors at the pre-game lobby communicator boundary.",
    ),
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def patched_entries(source_archive: Path, patches=PATCHES) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(source_archive) as source:
        for patch in patches:
            data = source.read(patch.entry)
            if _digest(data) != patch.source_sha256:
                raise ValueError(f"unsupported HoN resource entry: {patch.entry}")
            if data.count(patch.original) != 1:
                raise ValueError(f"resource patch anchor is not unique: {patch.entry}")
            result[patch.entry] = data.replace(patch.original, patch.replacement, 1)
    return result


def _marker(patches=PATCHES) -> bytes:
    payload = {
        "id": PATCH_ID,
        "version": "HoN 3.2.7.1",
        "reason": "Expose the dormant stock matchmaking interface to the ThorGor LAN backend.",
        "observed_failure": "The Matchmaking button is disabled and covered by an invisible blocker.",
        "discovered": "2026-08-24",
        "evidence": ["ui/scripts/main.lua", "ui/fe2/main.interface", "ui/scripts/matchmaking.lua"],
        "replacements": [
            {**asdict(item), "original": item.original.decode("utf-8"),
             "replacement": item.replacement.decode("utf-8")}
            for item in patches
        ],
    }
    return (json.dumps(payload, indent=2) + "\n").encode("utf-8")


def _archive_bytes(entries: dict[str, bytes], patches=PATCHES) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for name, data in sorted({**entries, MARKER_ENTRY: _marker(patches)}.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            target.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return stream.getvalue()


def verify_matchmaking_overlay(hon_home: Path, patches=PATCHES) -> str:
    overlay = hon_home / "game" / OVERLAY_ARCHIVE
    if not overlay.is_file():
        raise FileNotFoundError(f"matchmaking UI overlay is missing: {overlay}")
    expected = patched_entries(hon_home / "game" / SOURCE_ARCHIVE, patches)
    with zipfile.ZipFile(overlay) as archive:
        marker = json.loads(archive.read(MARKER_ENTRY))
        if marker.get("id") != PATCH_ID:
            raise ValueError(f"resources999.s2z is not owned by ThorGor: {overlay}")
        for name, data in expected.items():
            if archive.read(name) != data:
                raise ValueError(f"matchmaking UI overlay entry mismatch: {name}")
    return f"{OVERLAY_ARCHIVE} {_digest(overlay.read_bytes())}"


def install_matchmaking_overlay(hon_home: Path, patches=PATCHES) -> str:
    game = hon_home / "game"
    source = game / SOURCE_ARCHIVE
    overlay = game / OVERLAY_ARCHIVE
    if not source.is_file():
        raise FileNotFoundError(f"HoN resource archive not found: {source}")
    replacing = overlay.exists()
    if replacing:
        try:
            verify_matchmaking_overlay(hon_home, patches)
        except (KeyError, ValueError):
            with zipfile.ZipFile(overlay) as archive:
                marker = json.loads(archive.read(MARKER_ENTRY))
                if marker.get("id") != PATCH_ID:
                    raise ValueError(f"resources999.s2z is not owned by ThorGor: {overlay}")
        else:
            return "ThorGor matchmaking UI overlay is already installed."
    data = _archive_bytes(patched_entries(source, patches), patches)
    candidate = overlay.with_suffix(".s2z.thorgor.new")
    candidate.write_bytes(data)
    try:
        os.replace(candidate, overlay)
    finally:
        candidate.unlink(missing_ok=True)
    verify_matchmaking_overlay(hon_home, patches)
    action = "Updated" if replacing else "Installed"
    return f"{action} the reversible ThorGor matchmaking UI resource overlay."
