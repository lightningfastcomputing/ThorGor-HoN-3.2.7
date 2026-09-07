import argparse
import binascii
import json
import re
import select
import socket
import struct
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from thorgor.paths import ROOT


BASE_DIR = ROOT
STATE_FILE = BASE_DIR / "work" / "v31_registration_state.json"


@dataclass(frozen=True)
class ConnectC0:
    product: str
    version: str
    host_id: int
    connection_id: int
    password: str
    username: str
    cookie: str
    ip: str
    match_key: str
    invitation: str
    external_auth: bool
    flag_offset: int


def build_proxy_challenge(server_creation_timestamp: int, value: int) -> bytes:
    """Build the public-port authentication challenge used by COMPEL/K2."""
    if not 0 < server_creation_timestamp <= 0xFFFFFFFF:
        raise ValueError("server creation timestamp must be a nonzero uint32")
    if not 0 < value <= 0xFFFFFFFF:
        raise ValueError("challenge value must be a nonzero uint32")
    return (
        bytes(40)
        + b"\xff\xff\x40\x00"
        + struct.pack("<IHHHI", server_creation_timestamp, 60, 0xFFFF, 0xFFFF, value)
    )


def parse_lobby_create(data: bytes) -> dict[str, str] | None:
    """Extract the real 3.2.7.1 Create Game name/settings payload."""
    marker = b"\x00map:"
    marker_at = data.find(marker, 7)
    if marker_at < 0:
        return None
    name_start = marker_at
    while name_start > 7 and 0x20 <= data[name_start - 1] <= 0x7E:
        name_start -= 1
    if name_start == marker_at:
        return None
    settings_end = data.find(b"\x00", marker_at + 1)
    if settings_end < 0:
        return None
    try:
        match_name = data[name_start:marker_at].decode("utf-8", errors="strict")
        settings = data[marker_at + 1:settings_end].decode("ascii", errors="strict")
    except UnicodeDecodeError:
        return None
    fields = {key: value for key, value in re.findall(r"([a-z0-9_]+):(\S*)", settings)}
    if not match_name or not fields.get("map"):
        return None
    fields["mname"] = match_name
    fields["options"] = settings
    return fields


def parse_connect_c0(data: bytes) -> ConnectC0:
    """Parse the fixed leading fields consumed by Dedicated_ClientConnect."""
    if len(data) < 4 or data[:4] != b"\x00\x00\x01\xc0":
        raise ValueError("not a HoN C0 connection packet")

    cursor = 4

    def read_cstring(label: str) -> str:
        nonlocal cursor
        end = data.find(b"\x00", cursor)
        if end < 0:
            raise ValueError(f"unterminated {label}")
        try:
            value = data[cursor:end].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError(f"invalid UTF-8 in {label}") from exc
        cursor = end + 1
        return value

    product = read_cstring("product")
    version = read_cstring("version")
    if cursor + 6 > len(data):
        raise ValueError("truncated host or connection id")
    host_id, connection_id = struct.unpack_from("<IH", data, cursor)
    cursor += 6
    password = read_cstring("password")
    username = read_cstring("username")
    cookie = read_cstring("cookie")
    ip = read_cstring("ip")
    match_key = read_cstring("match key")
    invitation = read_cstring("invitation")
    if cursor >= len(data):
        raise ValueError("missing external-auth flag")
    flag_offset = cursor
    external_auth = bool(data[cursor] & 1)

    if product != "Heroes of Newerth" or version != "3.2.7.1":
        raise ValueError(f"unsupported product/version: {product!r} {version!r}")
    if not username or not cookie:
        raise ValueError("username and cookie are required")

    return ConnectC0(
        product=product,
        version=version,
        host_id=host_id,
        connection_id=connection_id,
        password=password,
        username=username,
        cookie=cookie,
        ip=ip,
        match_key=match_key,
        invitation=invitation,
        external_auth=external_auth,
        flag_offset=flag_offset,
    )


def validate_c_conn_response(wire: bytes, expected_cookie: str) -> tuple[bool, str]:
    """Accept only the typed identity fields required by the KONGOR contract."""
    try:
        cookie_bytes = expected_cookie.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return False, "cookie is not UTF-8"
    cookie_marker = (
        b's:6:"cookie";s:'
        + str(len(cookie_bytes)).encode("ascii")
        + b':"'
        + cookie_bytes
        + b'";'
    )
    if cookie_marker not in wire:
        return False, "response cookie did not match"
    account = re.search(rb's:10:"account_id";i:([1-9][0-9]*);', wire)
    if account is None:
        return False, "response has no positive integer account_id"
    game_cookie = re.search(rb's:11:"game_cookie";s:([1-9][0-9]*):"([^"\r\n]+)";', wire)
    if game_cookie is None or int(game_cookie.group(1)) != len(game_cookie.group(2)):
        return False, "response has no valid nonempty game_cookie"
    return True, f"account_id={account.group(1).decode('ascii')}"


def describe_trace_datagram(data: bytes) -> dict[str, object]:
    """Return compact, non-mutating K2 transport metadata for a datagram."""
    record: dict[str, object] = {
        "bytes": len(data),
        "prefix": data[:32].hex(),
    }
    if len(data) >= 7 and data[:3] == b"\x00\x00\x03":
        record["kind"] = "reliable_data"
        record["sequence"] = struct.unpack_from("<I", data, 3)[0]
        record["payload_bytes"] = len(data) - 7
        record["payload_prefix"] = data[7:23].hex()
        record["hex"] = data.hex()
    elif len(data) >= 7 and data[:3] == b"\x00\x00\x05":
        record["kind"] = "reliable_ack"
        record["sequence"] = struct.unpack_from("<I", data, 3)[0]
    elif len(data) >= 4 and data[:3] == b"\x00\x00\x01":
        record["kind"] = "control"
        record["command"] = data[3]
    else:
        record["kind"] = "raw"
        record["hex"] = data.hex()
    return record


PICKER_STATE_PREFIX = bytes.fromhex("5fb703905f0100ffffffff")
PICKER_HERO_BLOCK_IDS = tuple(range(3, 9))
CLIENT_TEAM_CHAT_PREFIX = b"\xc8\x5c"
SERVER_TEAM_CHAT_PREFIX = b"\x5f\x03"
SERVER_ALL_CHAT_PREFIX = b"\x5f\x02"
THORGOR_TEAM_CHAT_MARKER = b"[THORGOR_TEAM]"
CLIENT_TEAM_SELECTION_PREFIX = b"\xc8\x01"


def parse_client_team_chat(data: bytes) -> bytes | None:
    """Return the text from an exact 3.2.7.1 client team-chat event."""
    if len(data) < 7 + 5 or data[:3] != b"\x00\x00\x03":
        return None
    payload = data[7:]
    if not payload.startswith(CLIENT_TEAM_CHAT_PREFIX) or not payload.endswith(b"\x00\x01"):
        return None
    message = payload[len(CLIENT_TEAM_CHAT_PREFIX):-2]
    if not message or b"\x00" in message:
        return None
    return message


def parse_client_team_selection(data: bytes) -> tuple[int, int] | None:
    """Return the team and slot from an exact 3.2.7.1 lobby selection event."""
    if len(data) != 7 + 10 or data[:3] != b"\x00\x00\x03":
        return None
    payload = data[7:]
    if not payload.startswith(CLIENT_TEAM_SELECTION_PREFIX):
        return None
    team, slot = struct.unpack_from("<II", payload, 2)
    if team not in (1, 2) or not 0 <= slot <= 4:
        return None
    return team, slot


def team_chat_recipient_routes(
    sender_addr: tuple[str, int],
    team_by_route: dict[tuple[str, int], int],
    candidate_routes: Iterable[tuple[str, int]],
) -> tuple[tuple[str, int], ...]:
    """Select only active routes assigned to the sender's team."""
    sender_team = team_by_route.get(sender_addr)
    if sender_team is None:
        return ()
    return tuple(
        route_addr
        for route_addr in candidate_routes
        if team_by_route.get(route_addr) == sender_team
    )


def remember_reliable_sequence(
    observed: dict[int, float], sequence: int, now: float, ttl: float = 30.0
) -> bool:
    """Remember a reliable event once while allowing its transport retries."""
    cutoff = now - ttl
    expired = [item for item, observed_at in observed.items() if observed_at < cutoff]
    for item in expired:
        observed.pop(item, None)
    if sequence in observed:
        return False
    observed[sequence] = now
    return True


def parse_server_team_chat(data: bytes) -> tuple[int, bytes] | None:
    """Return sender number and text from an exact server team-chat event."""
    if len(data) < 7 + 5 or data[:3] != b"\x00\x00\x03":
        return None
    payload = data[7:]
    if not payload.startswith(SERVER_TEAM_CHAT_PREFIX) or not payload.endswith(b"\x00"):
        return None
    sender = payload[2]
    message = payload[3:-1]
    if not message or b"\x00" in message:
        return None
    return sender, message


def make_visible_team_chat_packet(sequence: int, sender_number: int, message: bytes) -> bytes:
    """Build one private UI-routed team-chat packet for a recipient."""
    safe_message = message.replace(b"\x00", b"")[:1024]
    payload = (
        SERVER_ALL_CHAT_PREFIX
        + bytes((sender_number & 0xFF,))
        + THORGOR_TEAM_CHAT_MARKER
        + safe_message
        + b"\x00"
    )
    return b"\x00\x00\x03" + struct.pack("<I", sequence & 0xFFFFFFFF) + payload


def make_joiner_team_chat_visible(data: bytes) -> bytes | None:
    """Convert a server-authorized joiner event for the UI team-chat shim."""
    parsed = parse_server_team_chat(data)
    if parsed is None:
        return None
    sender_number, message = parsed
    return make_visible_team_chat_packet(
        struct.unpack_from("<I", data, 3)[0], sender_number, message
    )


def rewrite_reliable_sequence(data: bytes, sequence: int) -> bytes:
    """Replace the sequence on a reliable data/ack packet without touching its payload."""
    if len(data) < 7 or data[:3] not in (b"\x00\x00\x03", b"\x00\x00\x05"):
        return data
    return data[:3] + struct.pack("<I", sequence & 0xFFFFFFFF) + data[7:]


def extract_picker_hero_block_suffix(data: bytes) -> tuple[bytes, tuple[int, ...]] | None:
    """Extract an exact, complete 3..8 hero-list suffix from a reliable packet."""
    if len(data) < 7 + len(PICKER_STATE_PREFIX) or data[:3] != b"\x00\x00\x03":
        return None
    payload = data[7:]
    if not payload.startswith(PICKER_STATE_PREFIX):
        return None
    cursor = len(PICKER_STATE_PREFIX)
    block_ids: list[int] = []
    while cursor < len(payload):
        if cursor + 5 > len(payload) or payload[cursor] != 0x60:
            return None
        block_id, block_size = struct.unpack_from("<HH", payload, cursor + 1)
        cursor += 5
        if block_size == 0 or block_size % 5 != 0 or cursor + block_size > len(payload):
            return None
        block_ids.append(block_id)
        cursor += block_size
    if tuple(block_ids) != PICKER_HERO_BLOCK_IDS:
        return None
    return payload[len(PICKER_STATE_PREFIX):], tuple(block_ids)


def repair_truncated_picker_packet(data: bytes, hero_suffix: bytes) -> bytes | None:
    """Append a validated cached suffix only to the exact truncated picker packet."""
    if not hero_suffix or len(data) != 7 + len(PICKER_STATE_PREFIX):
        return None
    if data[:3] != b"\x00\x00\x03" or data[7:] != PICKER_STATE_PREFIX:
        return None
    repaired = data + hero_suffix
    extracted = extract_picker_hero_block_suffix(repaired)
    if extracted is None or extracted[0] != hero_suffix:
        return None
    return repaired


def authorize_connect_c0(packet: ConnectC0, master_url: str, timeout: float) -> tuple[bool, str]:
    fields = {
        "f": "c_conn",
        "cookie": packet.cookie,
        "ip": packet.ip or "127.0.0.1",
    }
    # A client creating a public game connects with the acc_key returned by
    # gametype=90. Ordinary joiners do not receive that hosting key. Preserve
    # it so the backend can make the idle -> lobby transition on the real
    # 3.2.7.1 event instead of relying on a nonexistent start_game callback.
    if packet.match_key:
        fields["host_key"] = packet.match_key
    body = urlencode(fields).encode("ascii")
    request = Request(
        master_url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            wire = response.read(64 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, f"backend request failed: {exc}"
    return validate_c_conn_response(wire, packet.cookie)


def activate_host_lobby(
    packet: ConnectC0,
    lobby: dict[str, str],
    master_url: str,
    timeout: float,
) -> tuple[bool, str]:
    fields = {
        "f": "host_lobby",
        "cookie": packet.cookie,
        "host_key": packet.match_key,
        "version": packet.version,
        **lobby,
    }
    request = Request(
        master_url,
        data=urlencode(fields).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            wire = response.read(64 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, f"backend request failed: {exc}"
    match = re.search(rb's:8:"match_id";i:([1-9][0-9]*);', wire)
    if match is None:
        return False, "backend did not allocate a positive match_id"
    return True, f"match_id={match.group(1).decode('ascii')}"


def wait_for_native_start_game(match_id: int, timeout: float) -> tuple[bool, str]:
    """Wait until the manager bridge sends stock opcode 0x26 for this match."""
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            injected_for = int(state.get("native_start_game_injected_for", 0) or 0)
            if state.get("native_start_game_injected") and injected_for == match_id:
                return True, f"manager 0x26 acknowledged for match_id={match_id}"
            last_error = str(state.get("native_start_game_error") or "")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            last_error = repr(exc)
        time.sleep(0.025)
    suffix = f" last_error={last_error}" if last_error else ""
    return False, f"manager 0x26 timeout for match_id={match_id}{suffix}"


def release_host_reservation(
    packet: ConnectC0,
    master_url: str,
    timeout: float,
) -> tuple[bool, str]:
    request = Request(
        master_url,
        data=urlencode(
            {
                "f": "host_release",
                "cookie": packet.cookie,
                "host_key": packet.match_key,
            }
        ).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            wire = response.read(64 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, f"backend request failed: {exc}"
    if b's:7:"success";i:1;' not in wire:
        return False, "backend did not release reservation"
    return True, "released"


def make_authorized_local_c0(data: bytes, packet: ConnectC0) -> bytes:
    """Select the stock local-admission path after external c_conn approval."""
    if packet.flag_offset >= len(data):
        raise ValueError("external-auth flag offset is outside packet")
    rewritten = bytearray(data)
    rewritten[packet.flag_offset] &= 0xFE
    return bytes(rewritten)


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def format_packet(data: bytes) -> str:
    hex_text = binascii.hexlify(data).decode("ascii")
    grouped = " ".join(hex_text[i:i + 2] for i in range(0, len(hex_text), 2))
    ascii_text = "".join(chr(b) if 32 <= b <= 126 else "." for b in data)
    return f"len={len(data)} hex={grouped} ascii={ascii_text}"


def classify_packet(data: bytes) -> str:
    if len(data) >= 4 and data[:3] == b"\x00\x00\x01":
        return f"cmd=0x{data[3]:02x}({chr(data[3]) if 32 <= data[3] <= 126 else '?'})"
    return "cmd=raw"


def extract_cpacket_strings(data: bytes) -> list[str]:
    chunks: list[str] = []
    current = bytearray()
    for byte in data:
        if byte == 0:
            if current:
                try:
                    text = current.decode("utf-8", errors="strict")
                except UnicodeDecodeError:
                    text = ""
                if text and all(31 < ord(ch) < 127 for ch in text):
                    chunks.append(text)
            current.clear()
        else:
            current.append(byte)
    return chunks


def describe_special_packet(data: bytes) -> str:
    if len(data) < 4 or data[:3] != b"\x00\x00\x01":
        return ""

    command = data[3]
    payload = data[4:]
    strings = extract_cpacket_strings(payload)

    if command == 0xC0:
        labels = [
            "product",
            "version",
            "username",
            "cookie",
            "ip",
            "acc_key",
            "acc_key_short_hash",
            "acc_key_hash",
        ]
        paired = []
        for label, value in zip(labels, strings):
            paired.append(f"{label}={value!r}")
        if len(strings) > len(labels):
            paired.extend(f"extra_{index}={value!r}" for index, value in enumerate(strings[len(labels):], start=1))
        return "CONNECT_C0 " + " ".join(paired)

    if command == 0x51 and strings:
        return "SERVER_Q1 " + " ".join(f"text_{index}={value!r}" for index, value in enumerate(strings, start=1))

    if command in {0xC3, 0xC9}:
        return f"CONTROL_{command:02X}"

    return ""


# Stable compatibility exports. Implementations live behind focused protocol
# boundaries; the bridge below continues to expose the historical API.
from thorgor.protocols.admission import (
    activate_host_lobby,
    authorize_connect_c0,
    release_host_reservation,
    validate_c_conn_response,
)
from thorgor.protocols.packet_decoding import (
    ConnectC0,
    classify_packet,
    describe_special_packet,
    extract_cpacket_strings,
    format_packet,
    parse_connect_c0,
    parse_lobby_create,
)
from thorgor.protocols.tracing import (
    PICKER_HERO_BLOCK_IDS,
    PICKER_STATE_PREFIX,
    describe_trace_datagram,
    extract_picker_hero_block_suffix,
    repair_truncated_picker_packet,
)
from thorgor.protocols.transport import build_proxy_challenge, make_authorized_local_c0
from thorgor.protocols.routing import ClientRoute, RouteTable


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="UDP shim/logger for HoN browser and server traffic.")
    parser.add_argument(
        "--preset",
        choices=["thorgor-public-list"],
        help="Apply a known-good local preset for ThorGor public-list experiments.",
    )
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=11236)
    parser.add_argument("--target-host", default="127.0.0.1")
    parser.add_argument("--target-port", type=int, default=11235)
    parser.add_argument(
        "--master-url",
        default="http://127.0.0.1/server_requester.php",
        help="Local master-server endpoint used for c_conn authorization.",
    )
    parser.add_argument(
        "--require-c0-auth",
        action="store_true",
        help="Fail closed unless every C0 join is approved by the local c_conn endpoint.",
    )
    parser.add_argument("--auth-timeout", type=float, default=2.0)
    parser.add_argument(
        "--manager-start-timeout",
        type=float,
        default=3.0,
        help="Seconds to hold the final Create Game packet for manager opcode 0x26.",
    )
    parser.add_argument("--log-file", default="work/hon_udp_shim.log")
    parser.add_argument(
        "--packet-log",
        action="store_true",
        help="Log every UDP packet with full hex/ASCII. Disabled by default because it can add severe jitter.",
    )
    parser.add_argument(
        "--stats-interval",
        type=float,
        default=1.0,
        help="Seconds between compact packet-rate statistics. Set 0 to disable.",
    )
    parser.add_argument(
        "--admission-trace-seconds",
        type=float,
        default=5.0,
        help="Buffer a capped packet transcript after each authorized C0, then append it in one batch. Set 0 to disable.",
    )
    parser.add_argument(
        "--admission-trace-packets",
        type=int,
        default=128,
        help="Maximum packets retained per direction for each admission transcript.",
    )
    parser.add_argument(
        "--route-trace-seconds",
        type=float,
        default=0.0,
        help="Passively capture each authenticated route for this many seconds. Set 0 to disable.",
    )
    parser.add_argument(
        "--route-trace-packets",
        type=int,
        default=20000,
        help="Maximum non-keepalive packets retained per direction in a route trace.",
    )
    parser.add_argument(
        "--route-trace-checkpoint-seconds",
        type=float,
        default=1.0,
        help="Seconds between batched route-trace writes.",
    )
    parser.add_argument(
        "--route-trace-dir",
        default="work/route_traces",
        help="Directory for passive per-route JSONL captures and summaries.",
    )
    parser.add_argument(
        "--repair-joiner-hero-blocks",
        action="store_true",
        help="Repair only the exact truncated picking packet using validated host blocks 3 through 8.",
    )
    parser.add_argument(
        "--joiner-team-chat-fallback",
        action="store_true",
        help="Render team chat through the generic message event when a joiner's sender registry is incomplete.",
    )
    parser.add_argument("--idle-timeout", type=float, default=120.0)
    parser.add_argument(
        "--client-route-timeout",
        type=float,
        default=600.0,
        help="Seconds of inactivity before an isolated client-to-server UDP route is closed.",
    )
    parser.add_argument(
        "--max-client-routes",
        type=int,
        default=16,
        help="Maximum simultaneous authenticated client UDP routes.",
    )
    parser.add_argument(
        "--unique-loopback-sources",
        action="store_true",
        help="Bind each upstream route to a distinct 127.x source IP so native client lookup cannot collide.",
    )
    parser.add_argument(
        "--proxy-challenge",
        action="store_true",
        help="Authenticate public-port clients with the native K2 proxy challenge.",
    )
    parser.add_argument(
        "--proxy-challenge-interval",
        type=float,
        default=10.0,
        help="Seconds between public-port challenge renewals.",
    )
    parser.add_argument(
        "--browser-reply-timeout",
        type=float,
        default=1.5,
        help="Seconds to wait before logging that a forwarded HoN browser probe received no server reply.",
    )
    parser.add_argument(
        "--answer-browser-o",
        action="store_true",
        help="Answer HoN browser 0xCA probes directly with a minimal synthetic 'o' reply.",
    )
    parser.add_argument(
        "--answer-browser-f",
        action="store_true",
        help="Answer HoN browser 0xCA probes directly with an experimental synthetic 'f' reply.",
    )
    parser.add_argument(
        "--answer-browser-both",
        action="store_true",
        help="Answer HoN browser 0xCA probes directly with synthetic 'o' and 'f' replies, in that order.",
    )
    parser.add_argument(
        "--no-forward-browser",
        action="store_true",
        help="Do not forward HoN browser 0xCA probes to the real server.",
    )
    parser.add_argument(
        "--browser-o-value",
        type=int,
        default=0,
        help="32-bit little-endian payload value for synthetic browser 'o' replies.",
    )
    parser.add_argument("--browser-name", default="Unnamed Server")
    parser.add_argument(
        "--browser-ip",
        default="client",
        help="IP string to return in the synthetic browser reply. Use 'client' to mirror the probing client address.",
    )
    parser.add_argument(
        "--browser-version",
        default="3.2.7",
        help="Version-like dotted triplet for the synthetic browser 'f' reply field the HoN client tokenizes.",
    )
    parser.add_argument("--browser-local-60c", default="")
    parser.add_argument("--browser-local-598", default="")
    parser.add_argument("--browser-map", default="caldavar")
    parser.add_argument("--browser-local-630", default="sandbox")
    parser.add_argument("--browser-local-5ec", default="normal")
    parser.add_argument("--browser-local-654", type=int, default=0)
    parser.add_argument("--browser-bvar2", type=int, default=0)
    parser.add_argument("--browser-local-55c", type=int, default=0)
    parser.add_argument("--browser-local-538", type=int, default=0)
    parser.add_argument("--browser-local-664", type=int, default=0)
    parser.add_argument("--browser-local-665", type=int, default=0)
    parser.add_argument("--browser-local-655", type=int, default=0)
    parser.add_argument("--browser-local-57c", type=int, default=0)
    parser.add_argument("--browser-local-660", type=int, default=0)
    parser.add_argument("--browser-local-558", type=int, default=10)
    parser.add_argument("--browser-local-5f0", type=int, default=0)
    parser.add_argument("--browser-local-65c", type=int, default=0)
    parser.add_argument(
        "--registration-state-file",
        default="work/v31_registration_state.json",
        help="Backend state used to switch the browser reply between idle-vessel and live-lobby forms.",
    )
    parser.add_argument(
        "--bootstrap-route",
        action="append",
        default=[],
        metavar="CLIENT_IP:CLIENT_PORT:UPSTREAM_PORT",
        help="Restore an existing client/upstream UDP tuple during a bridge-only hot restart.",
    )
    cli_args = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(cli_args)
    browser_ip_explicit = any(
        item == "--browser-ip" or item.startswith("--browser-ip=")
        for item in cli_args
    )

    if args.preset == "thorgor-public-list":
        args.listen_port = 11236
        args.target_host = "127.0.0.1"
        args.target_port = 11235
        args.log_file = "work/hon_udp_shim_public_list.log"
        args.answer_browser_f = True
        args.answer_browser_o = False
        args.answer_browser_both = False
        args.no_forward_browser = True
        args.browser_name = "Unnamed Game"
        if not browser_ip_explicit:
            args.browser_ip = "127.0.0.1"
        args.browser_version = "3.2.7"
        args.browser_map = "caldavar"
        # Ghidra shows this field is effectively checked as empty-vs-nonempty mode state.
        # For the public browser path, try the empty variant first.
        args.browser_local_60c = ""
        args.browser_local_598 = "caldavar"
        # 3.2.7.1 renders this wire field as the public-browser game name.
        args.browser_local_630 = "Unnamed Game"
        args.browser_local_5ec = "normal"
        # These two leading bytes are current players / maximum players.
        args.browser_local_654 = 1
        args.browser_bvar2 = 10
        # This short is the browser's minimum-PSR column, not the slot count.
        args.browser_local_558 = 0
        args.require_c0_auth = True
        # K2's client lookup compares source IP plus the pre-admission connection
        # ID. Every C0 starts with ID zero, so distinct UDP source ports alone do
        # not distinguish multiple clients behind the loopback bridge.
        args.unique_loopback_sources = True
        # COMPEL's proxy challenge is required by newer public-port clients,
        # but the 3.2.7.1 CPacket path rejects that 58-byte frame as fatal.
        args.proxy_challenge = False
        args.joiner_team_chat_fallback = True

    log_path = Path(args.log_file)
    if not log_path.is_absolute():
        log_path = BASE_DIR / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    state_path = Path(args.registration_state_file)
    if not state_path.is_absolute():
        state_path = BASE_DIR / state_path

    def log(line: str) -> None:
        text = f"{now_text()} | {line}"
        print(text, flush=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if hasattr(socket, "SIO_UDP_CONNRESET"):
        client_sock.ioctl(socket.SIO_UDP_CONNRESET, False)
    client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client_sock.bind((args.listen_host, args.listen_port))
    client_sock.setblocking(False)

    target = (args.target_host, args.target_port)
    last_activity = time.time()
    # Each client endpoint needs its own upstream socket.  Reusing one socket
    # makes every local client appear to K2 as the same UDP peer and makes
    # server replies impossible to route deterministically.
    upstream_by_client: dict[tuple[str, int], socket.socket] = {}
    routes = RouteTable(args.max_client_routes)
    client_by_upstream: dict[socket.socket, tuple[str, int]] = {}
    route_activity: dict[tuple[str, int], float] = {}
    route_connect: dict[tuple[str, int], ConnectC0] = {}
    route_counters: dict[tuple[str, int], dict[str, int]] = {}
    route_challenge_at: dict[tuple[str, int], float] = {}
    route_source_ip: dict[tuple[str, int], str] = {}
    admission_traces: dict[tuple[str, int], dict[str, object]] = {}
    route_traces: dict[tuple[str, int], dict[str, object]] = {}
    route_trace_dir = BASE_DIR / args.route_trace_dir
    if args.route_trace_seconds > 0:
        route_trace_dir.mkdir(parents=True, exist_ok=True)
    challenge_sequence = 0
    pending_browser_queries: dict[bytes, dict[str, object]] = {}
    cached_picker_hero_suffix: bytes | None = None
    pending_team_chat: list[tuple[float, bytes, str, tuple[str, int]]] = []
    team_chat_sender_names: dict[int, str] = {}
    route_team: dict[tuple[str, int], int] = {}
    route_player_number: dict[tuple[str, int], int] = {}
    handled_team_chat_sequences: dict[tuple[str, int], dict[int, float]] = {}
    server_sequence_offset: dict[tuple[str, int], int] = {}
    last_server_sequence: dict[tuple[str, int], int] = {}
    server_sequence_translation: dict[tuple[str, int], dict[int, int]] = {}
    # Maps client-visible reliable numbers back to server numbers. None denotes
    # a shim-generated packet whose acknowledgement must not reach the server.
    server_ack_translation: dict[tuple[str, int], dict[int, int | None]] = {}

    # Keep the forwarding hot path quiet. Full per-packet formatting, console flushes,
    # and opening/closing a log file for every datagram caused visible gameplay jitter.
    counters = {
        "client_rx": 0, "client_rx_bytes": 0,
        "server_tx": 0, "server_tx_bytes": 0,
        "server_rx": 0, "server_rx_bytes": 0,
        "client_tx": 0, "client_tx_bytes": 0,
    }
    stats_last = time.monotonic()

    log(
        f"LISTEN {client_sock.getsockname()[0]}:{client_sock.getsockname()[1]} -> TARGET {args.target_host}:{args.target_port} "
        f"(isolated per-client upstream sockets; max routes {args.max_client_routes})"
    )
    if args.preset:
        log(f"PRESET {args.preset}")
    if args.joiner_team_chat_fallback:
        log("JOINER_TEAM_CHAT_FALLBACK enabled")
    if args.require_c0_auth:
        log(f"C0_AUTH required endpoint={args.master_url!r} timeout={args.auth_timeout:.2f}s")
    if args.answer_browser_f or args.answer_browser_both:
        log(
            "BROWSER_F "
            f"name={args.browser_name!r} ip={args.browser_ip!r} local_60c={args.browser_local_60c!r} "
            f"version={args.browser_version!r} local_598={args.browser_local_598!r} "
            f"map={args.browser_map!r} local_630={args.browser_local_630!r} local_5ec={args.browser_local_5ec!r} "
            f"flags=654:{args.browser_local_654} b:{args.browser_bvar2} 55c:{args.browser_local_55c} "
            f"538:{args.browser_local_538} 664:{args.browser_local_664} 665:{args.browser_local_665} "
            f"655:{args.browser_local_655} 57c:{args.browser_local_57c} 660:{args.browser_local_660} "
            f"558:{args.browser_local_558} 5f0:{args.browser_local_5f0} 65c:{args.browser_local_65c}"
        )
    if args.answer_browser_o or args.answer_browser_both:
        log(f"BROWSER_O value={args.browser_o_value}")

    def encode_cpacket_wstring(text: str) -> bytes:
        return text.encode("utf-8") + b"\x00"

    def close_route(client_addr: tuple[str, int], reason: str) -> None:
        flush_admission_trace(client_addr, f"route_close:{reason}")
        flush_route_trace(client_addr, f"route_close:{reason}")
        upstream = upstream_by_client.pop(client_addr, None)
        routes.remove(client_addr)
        route_activity.pop(client_addr, None)
        route_connect.pop(client_addr, None)
        route_counters.pop(client_addr, None)
        route_challenge_at.pop(client_addr, None)
        server_sequence_offset.pop(client_addr, None)
        last_server_sequence.pop(client_addr, None)
        server_sequence_translation.pop(client_addr, None)
        server_ack_translation.pop(client_addr, None)
        route_team.pop(client_addr, None)
        route_player_number.pop(client_addr, None)
        handled_team_chat_sequences.pop(client_addr, None)
        source_ip = route_source_ip.pop(client_addr, "0.0.0.0")
        if upstream is None:
            return
        client_by_upstream.pop(upstream, None)
        local_port = upstream.getsockname()[1]
        upstream.close()
        log(
            f"ROUTE_CLOSE client={client_addr[0]}:{client_addr[1]} "
            f"upstream={source_ip}:{local_port} reason={reason} routes={len(upstream_by_client)}"
        )

    def begin_admission_trace(client_addr: tuple[str, int], username: str) -> None:
        if args.admission_trace_seconds <= 0 or args.admission_trace_packets <= 0:
            return
        started = time.monotonic()
        admission_traces[client_addr] = {
            "username": username,
            "started": started,
            "deadline": started + args.admission_trace_seconds,
            "to_server": [],
            "from_server": [],
        }

    def capture_admission_packet(client_addr: tuple[str, int], direction: str, data: bytes) -> None:
        trace = admission_traces.get(client_addr)
        if trace is None:
            return
        packets = trace[direction]
        if len(packets) >= args.admission_trace_packets:
            return
        elapsed_ms = int((time.monotonic() - trace["started"]) * 1000)
        packets.append(
            f"dt_ms={elapsed_ms} bytes={len(data)} {classify_packet(data)} hex={data.hex()}"
        )

    def flush_admission_trace(client_addr: tuple[str, int], reason: str) -> None:
        trace = admission_traces.pop(client_addr, None)
        if trace is None:
            return
        username = trace["username"]
        to_server = trace["to_server"]
        from_server = trace["from_server"]
        stamp = now_text()
        lines = [
            f"{stamp} | ADMISSION_TRACE_BEGIN client={client_addr[0]}:{client_addr[1]} "
            f"user={username!r} reason={reason} to_server={len(to_server)} from_server={len(from_server)}"
        ]
        lines.extend(
            f"{stamp} | ADMISSION_PACKET client={client_addr[0]}:{client_addr[1]} direction=to_server {packet}"
            for packet in to_server
        )
        lines.extend(
            f"{stamp} | ADMISSION_PACKET client={client_addr[0]}:{client_addr[1]} direction=from_server {packet}"
            for packet in from_server
        )
        lines.append(
            f"{stamp} | ADMISSION_TRACE_END client={client_addr[0]}:{client_addr[1]} user={username!r}"
        )
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        print(
            f"{stamp} | ADMISSION_TRACE_SAVED client={client_addr[0]}:{client_addr[1]} "
            f"user={username!r} reason={reason} to_server={len(to_server)} from_server={len(from_server)}",
            flush=True,
        )

    def start_route_trace(client_addr: tuple[str, int], username: str) -> None:
        if args.route_trace_seconds <= 0 or args.route_trace_packets <= 0:
            return
        flush_route_trace(client_addr, "replaced_by_new_c0")
        started = time.monotonic()
        safe_user = re.sub(r"[^A-Za-z0-9_.-]+", "_", username)[:48] or "unknown"
        stamp = time.strftime("%Y%m%d_%H%M%S")
        stem = f"route_{stamp}_{safe_user}_{client_addr[0].replace('.', '-')}_{client_addr[1]}"
        route_traces[client_addr] = {
            "username": username,
            "started": started,
            "deadline": started + args.route_trace_seconds,
            "next_checkpoint": started + max(args.route_trace_checkpoint_seconds, 0.1),
            "path": route_trace_dir / f"{stem}.jsonl",
            "summary_path": route_trace_dir / f"{stem}_summary.json",
            "pending": [],
            "stored": {"to_server": 0, "from_server": 0},
            "seen": {"to_server": 0, "from_server": 0},
            "bytes": {"to_server": 0, "from_server": 0},
            "kinds": {},
            "server_reliable_sequences": [],
            "client_ack_sequences": [],
            "server_payload_prefixes": {},
        }
        route_traces[client_addr]["pending"].append({
            "type": "route_trace_begin",
            "username": username,
            "client": f"{client_addr[0]}:{client_addr[1]}",
            "duration_seconds": args.route_trace_seconds,
            "format": "ThorGor passive route trace v73",
        })
        checkpoint_route_trace(client_addr)
        log(
            f"ROUTE_TRACE_BEGIN client={client_addr[0]}:{client_addr[1]} "
            f"user={username!r} seconds={args.route_trace_seconds:.1f}"
        )

    def capture_route_packet(client_addr: tuple[str, int], direction: str, data: bytes) -> None:
        trace = route_traces.get(client_addr)
        if trace is None:
            return
        trace["seen"][direction] += 1
        trace["bytes"][direction] += len(data)
        metadata = describe_trace_datagram(data)
        kind = str(metadata["kind"])
        kind_key = f"{direction}:{kind}"
        trace["kinds"][kind_key] = trace["kinds"].get(kind_key, 0) + 1

        if direction == "from_server" and kind == "reliable_data":
            trace["server_reliable_sequences"].append(int(metadata["sequence"]))
            payload_prefix = str(metadata.get("payload_prefix", ""))[:2] or "empty"
            trace["server_payload_prefixes"][payload_prefix] = (
                trace["server_payload_prefixes"].get(payload_prefix, 0) + 1
            )
        elif direction == "to_server" and kind == "reliable_ack":
            trace["client_ack_sequences"].append(int(metadata["sequence"]))

        # C9 keepalives dominate the stream and carry no state payload. Count
        # them in the summary but do not duplicate them in the evidence file.
        if kind == "control" and metadata.get("command") == 0xC9:
            return
        if trace["stored"][direction] >= args.route_trace_packets:
            return
        trace["stored"][direction] += 1
        trace["pending"].append({
            "type": "packet",
            "dt_ms": int((time.monotonic() - trace["started"]) * 1000),
            "direction": direction,
            **metadata,
        })

    def checkpoint_route_trace(client_addr: tuple[str, int]) -> None:
        trace = route_traces.get(client_addr)
        if trace is None or not trace["pending"]:
            return
        pending = trace["pending"]
        trace["pending"] = []
        with trace["path"].open("a", encoding="utf-8") as handle:
            for record in pending:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    def flush_route_trace(client_addr: tuple[str, int], reason: str) -> None:
        trace = route_traces.get(client_addr)
        if trace is None:
            return
        checkpoint_route_trace(client_addr)
        server_sequences = sorted(set(trace["server_reliable_sequences"]))
        gaps = [
            [previous, current]
            for previous, current in zip(server_sequences, server_sequences[1:])
            if current != previous + 1
        ]
        summary = {
            "format": "ThorGor passive route trace v73",
            "username": trace["username"],
            "client": f"{client_addr[0]}:{client_addr[1]}",
            "reason": reason,
            "elapsed_seconds": round(time.monotonic() - trace["started"], 3),
            "seen_packets": trace["seen"],
            "seen_bytes": trace["bytes"],
            "stored_packets": trace["stored"],
            "truncated": {
                direction: trace["stored"][direction] >= args.route_trace_packets
                for direction in ("to_server", "from_server")
            },
            "kinds": trace["kinds"],
            "server_reliable": {
                "count": len(trace["server_reliable_sequences"]),
                "unique_count": len(server_sequences),
                "first": server_sequences[0] if server_sequences else None,
                "last": server_sequences[-1] if server_sequences else None,
                "gaps": gaps,
                "payload_first_byte_counts": trace["server_payload_prefixes"],
            },
            "client_reliable_acks": {
                "count": len(trace["client_ack_sequences"]),
                "unique_count": len(set(trace["client_ack_sequences"])),
                "last": max(trace["client_ack_sequences"], default=None),
            },
            "trace_file": trace["path"].name,
        }
        trace["summary_path"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
        route_traces.pop(client_addr, None)
        log(
            f"ROUTE_TRACE_SAVED client={client_addr[0]}:{client_addr[1]} "
            f"user={trace['username']!r} reason={reason} "
            f"server_reliable={len(trace['server_reliable_sequences'])} "
            f"file={trace['path'].name!r}"
        )

    def send_proxy_challenge(client_addr: tuple[str, int]) -> None:
        nonlocal challenge_sequence
        if not args.proxy_challenge:
            return
        challenge_sequence = (challenge_sequence + 1) & 0xFFFFFFFF
        if challenge_sequence == 0:
            challenge_sequence = 1
        challenge = build_proxy_challenge(challenge_sequence, challenge_sequence)
        sent = client_sock.sendto(challenge, client_addr)
        route_challenge_at[client_addr] = time.time()
        log(
            f"PROXY_CHALLENGE client={client_addr[0]}:{client_addr[1]} "
            f"sequence={challenge_sequence} sent={sent}"
        )

    def maybe_repair_joiner_picker_packet(
        client_addr: tuple[str, int], data: bytes
    ) -> bytes:
        nonlocal cached_picker_hero_suffix
        if not args.repair_joiner_hero_blocks:
            return data

        extracted = extract_picker_hero_block_suffix(data)
        if extracted is not None:
            suffix, block_ids = extracted
            connect = route_connect.get(client_addr)
            if connect is not None and connect.match_key:
                cached_picker_hero_suffix = suffix
                log(
                    f"HERO_BLOCK_CACHE client={client_addr[0]}:{client_addr[1]} "
                    f"user={connect.username!r} blocks={list(block_ids)} suffix_bytes={len(suffix)}"
                )
            return data

        connect = route_connect.get(client_addr)
        if connect is None or connect.match_key or cached_picker_hero_suffix is None:
            return data
        repaired = repair_truncated_picker_packet(data, cached_picker_hero_suffix)
        if repaired is None:
            return data
        log(
            f"JOINER_HERO_BLOCK_REPAIR client={client_addr[0]}:{client_addr[1]} "
            f"user={connect.username!r} original_bytes={len(data)} repaired_bytes={len(repaired)} "
            f"blocks={list(PICKER_HERO_BLOCK_IDS)}"
        )
        return repaired

    def allocate_route_source_ip() -> str:
        if not args.unique_loopback_sources:
            return "0.0.0.0"
        used = set(route_source_ip.values())
        for final_octet in range(2, 255):
            candidate = f"127.0.0.{final_octet}"
            if candidate not in used:
                return candidate
        raise RuntimeError("no unique loopback source IP remains")

    def get_or_create_route(client_addr: tuple[str, int]) -> socket.socket:
        existing = upstream_by_client.get(client_addr)
        if existing is not None:
            route_activity[client_addr] = time.time()
            return existing
        if len(upstream_by_client) >= args.max_client_routes:
            oldest_client = min(route_activity, key=route_activity.__getitem__)
            close_route(oldest_client, "route_limit_lru")
        upstream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if hasattr(socket, "SIO_UDP_CONNRESET"):
            upstream.ioctl(socket.SIO_UDP_CONNRESET, False)
        source_ip = allocate_route_source_ip()
        upstream.bind((source_ip, 0))
        upstream.setblocking(False)
        upstream_by_client[client_addr] = upstream
        routes.add(ClientRoute(client_addr, upstream, source_ip))
        client_by_upstream[upstream] = client_addr
        route_activity[client_addr] = time.time()
        route_source_ip[client_addr] = source_ip
        route_counters[client_addr] = {
            "to_server": 0,
            "to_server_bytes": 0,
            "from_server": 0,
            "from_server_bytes": 0,
        }
        log(
            f"ROUTE_OPEN client={client_addr[0]}:{client_addr[1]} "
            f"upstream={upstream.getsockname()[0]}:{upstream.getsockname()[1]} "
            f"target={target[0]}:{target[1]} routes={len(upstream_by_client)}"
        )
        send_proxy_challenge(client_addr)
        return upstream

    def inject_visible_team_chat(
        recipient_addr: tuple[str, int],
        sender_number: int,
        message: bytes,
        sender_name: str,
        reason: str,
    ) -> bool:
        """Insert one private chat event into a recipient's reliable stream."""
        previous = last_server_sequence.get(recipient_addr)
        if previous is None:
            log(
                f"JOINER_TEAM_CHAT_MIRROR_SKIPPED client={recipient_addr[0]}:{recipient_addr[1]} "
                "reason=no server reliable sequence"
            )
            return False
        offset = server_sequence_offset.get(recipient_addr, 0) + 1
        server_sequence_offset[recipient_addr] = offset
        visible_sequence = (previous + 1) & 0xFFFFFFFF
        last_server_sequence[recipient_addr] = visible_sequence
        visible = make_visible_team_chat_packet(visible_sequence, sender_number, message)
        server_ack_translation.setdefault(recipient_addr, {})[visible_sequence] = None
        sent_visible = client_sock.sendto(visible, recipient_addr)
        counters["client_tx"] += 1
        counters["client_tx_bytes"] += sent_visible
        log(
            f"JOINER_TEAM_CHAT_MIRRORED client={recipient_addr[0]}:{recipient_addr[1]} "
            f"sender={sender_number} name={sender_name!r} team={route_team.get(recipient_addr)} "
            f"reason={reason} sequence={visible_sequence} bytes={sent_visible}"
        )
        return True

    def make_browser_o_reply(query: bytes) -> bytes | None:
        if len(query) != 6 or query[:3] != b"\x00\x00\x01" or query[3] != 0xCA:
            return None
        # Experimental browser reply:
        # prefix 00 00 01 + command 'o' + 32-bit payload.
        return b"\x00\x00\x01" + bytes([ord("o")]) + args.browser_o_value.to_bytes(4, "little", signed=True)

    def make_browser_f_reply(query: bytes, client_addr: tuple[str, int]) -> bytes | None:
        if len(query) != 6 or query[:3] != b"\x00\x00\x01" or query[3] != 0xCA:
            return None

        token = query[4:6]
        client_ip = client_addr[0] if args.browser_ip == "client" else args.browser_ip
        state: dict[str, object] = {}
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            pass
        try:
            lobby_active = int(state.get("match_id", 0)) > 0
        except (TypeError, ValueError):
            lobby_active = False
        browser_name = str(state.get("match_name") or args.browser_name)
        browser_map = str(state.get("match_map") or args.browser_local_598)
        # FUN_15307650 accepts an empty local_60c only for the create-server
        # query and a nonempty value only for the join-game query.
        # This is the active map name, not the backend match ID. The client's
        # join browser uses this field both as the idle/lobby discriminator and
        # as its pre-query map filter.
        browser_local_60c = browser_map if lobby_active else ""

        payload = bytearray()
        payload += token
        payload += encode_cpacket_wstring(browser_name)
        payload += bytes([args.browser_local_654 & 0xFF])
        payload += bytes([args.browser_bvar2 & 0xFF])
        payload += encode_cpacket_wstring(browser_local_60c)
        # Ghidra shows this field is tokenized into three numeric components on the client,
        # which fits a version triplet much better than an IP string.
        payload += encode_cpacket_wstring(args.browser_version)
        payload += bytes([args.browser_local_55c & 0xFF])
        payload += bytes([args.browser_local_538 & 0xFF])
        payload += bytes([args.browser_local_664 & 0xFF])
        payload += bytes([args.browser_local_665 & 0xFF])
        payload += encode_cpacket_wstring(browser_map)
        payload += encode_cpacket_wstring(browser_name)
        payload += encode_cpacket_wstring(args.browser_local_5ec)
        payload += bytes([args.browser_local_655 & 0xFF])
        payload += args.browser_local_57c.to_bytes(4, "little", signed=True)
        payload += bytes([args.browser_local_660 & 0xFF])
        payload += args.browser_local_558.to_bytes(2, "little", signed=False)
        payload += args.browser_local_5f0.to_bytes(2, "little", signed=False)
        payload += bytes([args.browser_local_65c & 0xFF])
        return b"\x00\x00\x01" + bytes([ord("f")]) + payload

    for route in args.bootstrap_route:
        try:
            route_ip, route_client_port, route_upstream_port = route.rsplit(":", 2)
            client_addr = (route_ip, int(route_client_port))
            upstream_port = int(route_upstream_port)
            if client_addr in upstream_by_client:
                raise ValueError("duplicate client endpoint")
            upstream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            if hasattr(socket, "SIO_UDP_CONNRESET"):
                upstream.ioctl(socket.SIO_UDP_CONNRESET, False)
            source_ip = allocate_route_source_ip()
            upstream.bind((source_ip, upstream_port))
            upstream.setblocking(False)
            upstream_by_client[client_addr] = upstream
            routes.add(ClientRoute(client_addr, upstream, source_ip))
            client_by_upstream[upstream] = client_addr
            route_activity[client_addr] = time.time()
            route_source_ip[client_addr] = source_ip
            log(
                f"ROUTE_RESTORED client={client_addr[0]}:{client_addr[1]} "
                f"upstream={source_ip}:{upstream_port} routes={len(upstream_by_client)}"
            )
            send_proxy_challenge(client_addr)
        except (OSError, TypeError, ValueError) as exc:
            raise SystemExit(f"invalid --bootstrap-route {route!r}: {exc}") from exc

    while True:
        ready, _, _ = select.select([client_sock] + list(client_by_upstream), [], [], 0.25)
        now = time.time()
        stats_now = time.monotonic()
        for trace_client, trace in list(admission_traces.items()):
            if stats_now >= trace["deadline"]:
                flush_admission_trace(trace_client, "window_complete")
        for trace_client, trace in list(route_traces.items()):
            if stats_now >= trace["deadline"]:
                flush_route_trace(trace_client, "window_complete")
            elif stats_now >= trace["next_checkpoint"]:
                checkpoint_route_trace(trace_client)
                trace["next_checkpoint"] = stats_now + max(args.route_trace_checkpoint_seconds, 0.1)
        if args.stats_interval > 0 and stats_now - stats_last >= args.stats_interval:
            elapsed = max(stats_now - stats_last, 0.001)
            log(
                "STATS "
                f"routes={len(upstream_by_client)} "
                f"client_rx={counters['client_rx']/elapsed:.0f}pps/{counters['client_rx_bytes']/elapsed/1024:.1f}KiBps "
                f"server_tx={counters['server_tx']/elapsed:.0f}pps/{counters['server_tx_bytes']/elapsed/1024:.1f}KiBps "
                f"server_rx={counters['server_rx']/elapsed:.0f}pps/{counters['server_rx_bytes']/elapsed/1024:.1f}KiBps "
                f"client_tx={counters['client_tx']/elapsed:.0f}pps/{counters['client_tx_bytes']/elapsed/1024:.1f}KiBps"
            )
            for client_addr, route_counts in list(route_counters.items()):
                connect = route_connect.get(client_addr)
                username = connect.username if connect is not None else "-"
                upstream = upstream_by_client.get(client_addr)
                upstream_port = upstream.getsockname()[1] if upstream is not None else 0
                log(
                    "ROUTE_STATS "
                    f"client={client_addr[0]}:{client_addr[1]} user={username!r} "
                    f"upstream_port={upstream_port} "
                    f"to_server={route_counts['to_server']}pkt/{route_counts['to_server_bytes']}B "
                    f"from_server={route_counts['from_server']}pkt/{route_counts['from_server_bytes']}B"
                )
                for key in route_counts:
                    route_counts[key] = 0
            for key in counters:
                counters[key] = 0
            stats_last = stats_now
        expired_clients = [
            client_addr
            for client_addr, active_at in route_activity.items()
            if now - active_at >= args.client_route_timeout
        ]
        for client_addr in expired_clients:
            close_route(client_addr, "idle_timeout")
        if args.proxy_challenge:
            for client_addr in list(upstream_by_client):
                challenged_at = route_challenge_at.get(client_addr, 0.0)
                if now - challenged_at >= args.proxy_challenge_interval:
                    send_proxy_challenge(client_addr)
        expired_tokens: list[bytes] = []
        for token, info in pending_browser_queries.items():
            sent_at = float(info["sent_at"])
            if now - sent_at >= args.browser_reply_timeout:
                addr = info["client_addr"]
                log(
                    "BROWSER_TIMEOUT "
                    f"token={token.hex()} client={addr[0]}:{addr[1]} "
                    f"target={args.target_host}:{args.target_port} waited={now - sent_at:.3f}s"
                )
                expired_tokens.append(token)
        for token in expired_tokens:
            pending_browser_queries.pop(token, None)
        if not ready:
            if time.time() - last_activity > args.idle_timeout:
                log("IDLE timeout reached; still listening.")
                last_activity = time.time()
            continue

        for sock_obj in ready:
            if sock_obj is client_sock:
                try:
                    data, addr = client_sock.recvfrom(65535)
                except (ConnectionResetError, ConnectionAbortedError, OSError) as exc:
                    log(f"CLIENT_SOCKET_RECOVERED error={exc!r}")
                    continue
                last_activity = time.time()
                counters["client_rx"] += 1
                counters["client_rx_bytes"] += len(data)
                if args.packet_log:
                    log(f"CLIENT_RX {addr[0]}:{addr[1]} | {classify_packet(data)} | {format_packet(data)}")
                special = describe_special_packet(data)
                if special:
                    log(f"CLIENT_RX_DETAIL {addr[0]}:{addr[1]} | {special}")
                browser_replies: list[tuple[str, bytes]] = []
                if args.answer_browser_both:
                    browser_o_reply = make_browser_o_reply(data)
                    if browser_o_reply is not None:
                        browser_replies.append(("synthetic_o", browser_o_reply))
                    browser_f_reply = make_browser_f_reply(data, addr)
                    if browser_f_reply is not None:
                        browser_replies.append(("synthetic_f", browser_f_reply))
                elif args.answer_browser_f:
                    browser_f_reply = make_browser_f_reply(data, addr)
                    if browser_f_reply is not None:
                        browser_replies.append(("synthetic_f", browser_f_reply))
                elif args.answer_browser_o:
                    browser_o_reply = make_browser_o_reply(data)
                    if browser_o_reply is not None:
                        browser_replies.append(("synthetic_o", browser_o_reply))
                is_browser_query = (
                    len(data) == 6 and data[:3] == b"\x00\x00\x01" and data[3] == 0xCA
                )
                if is_browser_query:
                    log(f"BROWSER_RX client={addr[0]}:{addr[1]} token={data[4:6].hex()}")
                for reply_kind, browser_reply in browser_replies:
                    sent = client_sock.sendto(browser_reply, addr)
                    counters["client_tx"] += 1
                    counters["client_tx_bytes"] += sent
                    log(f"BROWSER_TX client={addr[0]}:{addr[1]} kind={reply_kind} bytes={sent} token={data[4:6].hex() if len(data) >= 6 else '-'}")
                    if args.packet_log:
                        log(f"CLIENT_TX_PACKET {addr[0]}:{addr[1]} | {format_packet(browser_reply)}")
                if is_browser_query and args.no_forward_browser:
                    log("SERVER_TX skipped for browser query")
                    continue
                if args.require_c0_auth and len(data) >= 4 and data[:4] == b"\x00\x00\x01\xc0":
                    try:
                        connect = parse_connect_c0(data)
                    except ValueError as exc:
                        log(f"C0_AUTH_REJECT client={addr[0]}:{addr[1]} reason={exc}")
                        continue
                    approved, reason, is_match_host = authorize_connect_c0(connect, args.master_url, args.auth_timeout)
                    if not approved:
                        log(
                            f"C0_AUTH_REJECT client={addr[0]}:{addr[1]} "
                            f"user={connect.username!r} reason={reason}"
                        )
                        continue
                    log(
                        f"C0_AUTH_ACCEPT client={addr[0]}:{addr[1]} user={connect.username!r} "
                        f"host_id=0x{connect.host_id:08X} connection_id=0x{connect.connection_id:04X} "
                        f"packet_ip={connect.ip!r} external={int(connect.external_auth)} {reason}"
                    )
                    log(
                        f"C0_WIRE client={addr[0]}:{addr[1]} user={connect.username!r} "
                        f"bytes={len(data)} flag_offset={connect.flag_offset} hex={data.hex()}"
                    )
                    data = make_authorized_local_c0(data, connect, is_match_host=is_match_host)
                    route_connect[addr] = connect
                    if addr not in route_player_number:
                        used_player_numbers = set(route_player_number.values())
                        route_player_number[addr] = next(
                            number for number in range(256) if number not in used_player_numbers
                        )
                    typed_route = routes.get(addr)
                    if typed_route is not None:
                        typed_route.connected = connect
                    begin_admission_trace(addr, connect.username)
                    start_route_trace(addr, connect.username)
                    log(
                        f"C0_AUTH_LOCALIZED client={addr[0]}:{addr[1]} "
                        f"flag_offset={connect.flag_offset} host_id_preserved=0x{connect.host_id:08X}"
                    )
                elif args.require_c0_auth and addr not in upstream_by_client:
                    log(
                        f"ROUTE_REJECT client={addr[0]}:{addr[1]} "
                        "reason=no authenticated C0 route"
                    )
                    continue
                if data == b"\x00\x00\x01\xc3":
                    host_connect = route_connect.get(addr)
                    if host_connect is not None and host_connect.match_key:
                        released, release_reason = release_host_reservation(
                            host_connect,
                            args.master_url,
                            args.auth_timeout,
                        )
                        log(
                            f"HOST_RESERVATION_{'RELEASED' if released else 'RELEASE_FAILED'} "
                            f"client={addr[0]}:{addr[1]} {release_reason}"
                        )
                team_selection = parse_client_team_selection(data)
                if team_selection is not None:
                    selected_team, selected_slot = team_selection
                    route_team[addr] = selected_team
                    connect = route_connect.get(addr)
                    selected_user = connect.username if connect is not None else "Player"
                    log(
                        f"PLAYER_TEAM client={addr[0]}:{addr[1]} "
                        f"user={selected_user!r} "
                        f"team={selected_team} slot={selected_slot}"
                    )
                team_message = parse_client_team_chat(data)
                if team_message is not None:
                    client_sequence = struct.unpack_from("<I", data, 3)[0]
                    handled = handled_team_chat_sequences.setdefault(addr, {})
                    if not remember_reliable_sequence(
                        handled, client_sequence, time.monotonic()
                    ):
                        team_message = None
                if team_message is not None:
                    connect = route_connect.get(addr)
                    sender_name = connect.username if connect is not None else "Player"
                    cutoff = time.monotonic() - 10.0
                    pending_team_chat[:] = [
                        item for item in pending_team_chat if item[0] >= cutoff
                    ]
                    pending_team_chat.append((time.monotonic(), team_message, sender_name, addr))
                    sender_team = route_team.get(addr)
                    host_team = next(
                        (
                            route_team.get(route_addr)
                            for route_addr, route_identity in route_connect.items()
                            if route_identity.match_key
                        ),
                        None,
                    )
                    # The dedicated server only exposes a usable team-chat echo
                    # through the host's route. When a joiner is on the other
                    # team, deliver that team's event privately here instead.
                    if (
                        args.joiner_team_chat_fallback
                        and connect is not None
                        and not connect.match_key
                        and sender_team is not None
                        and host_team is not None
                        and sender_team != host_team
                    ):
                        sender_number = route_player_number.get(addr, 0)
                        candidates = (
                            teammate_addr
                            for teammate_addr, teammate_connect in tuple(route_connect.items())
                            if not teammate_connect.match_key
                            and teammate_addr in upstream_by_client
                        )
                        for teammate_addr in team_chat_recipient_routes(
                            addr, route_team, candidates
                        ):
                            if teammate_addr not in upstream_by_client:
                                continue
                            inject_visible_team_chat(
                                teammate_addr,
                                sender_number,
                                team_message,
                                sender_name,
                                "opposing_joiner_team",
                            )
                lobby = parse_lobby_create(data)
                host_connect = route_connect.get(addr)
                if lobby is not None and host_connect is not None and host_connect.match_key:
                    activated, activation_reason = activate_host_lobby(
                        host_connect,
                        lobby,
                        args.master_url,
                        args.auth_timeout,
                    )
                    log(
                        f"HOST_LOBBY_{'ACTIVATED' if activated else 'REJECTED'} "
                        f"client={addr[0]}:{addr[1]} name={lobby['mname']!r} "
                        f"map={lobby['map']!r} {activation_reason}"
                    )
                    if activated:
                        match_id = int(activation_reason.rsplit("=", 1)[-1])
                        started, start_reason = wait_for_native_start_game(
                            match_id, args.manager_start_timeout
                        )
                        log(
                            f"HOST_LOBBY_MANAGER_START_{'READY' if started else 'TIMEOUT'} "
                            f"client={addr[0]}:{addr[1]} {start_reason}"
                        )
                upstream = get_or_create_route(addr)
                route_activity[addr] = time.time()
                capture_admission_packet(addr, "to_server", data)
                capture_route_packet(addr, "to_server", data)
                if len(data) >= 7 and data[:3] == b"\x00\x00\x05":
                    visible_ack = struct.unpack_from("<I", data, 3)[0]
                    translations = server_ack_translation.get(addr, {})
                    if visible_ack in translations:
                        original_ack = translations[visible_ack]
                        if original_ack is None:
                            log(
                                f"JOINER_TEAM_CHAT_ACK client={addr[0]}:{addr[1]} "
                                f"sequence={visible_ack}"
                            )
                            continue
                        data = rewrite_reliable_sequence(data, original_ack)
                sent = upstream.sendto(data, target)
                counters["server_tx"] += 1
                counters["server_tx_bytes"] += sent
                route_counts = route_counters.get(addr)
                if route_counts is not None:
                    route_counts["to_server"] += 1
                    route_counts["to_server_bytes"] += sent
                if args.packet_log:
                    log(
                        f"SERVER_TX {target[0]}:{target[1]} | client={addr[0]}:{addr[1]} "
                        f"upstream_port={upstream.getsockname()[1]} forwarded={sent}"
                    )
                if is_browser_query:
                    token = data[4:6]
                    pending_browser_queries[token] = {
                        "sent_at": time.time(),
                        "client_addr": addr,
                        "query": data,
                    }
                    log(
                        "BROWSER_FORWARD "
                        f"token={token.hex()} client={addr[0]}:{addr[1]} "
                        f"target={target[0]}:{target[1]}"
                    )
            else:
                upstream = sock_obj
                client_addr = client_by_upstream.get(upstream)
                if client_addr is None:
                    continue
                try:
                    data, addr = upstream.recvfrom(65535)
                except (ConnectionResetError, ConnectionAbortedError, OSError) as exc:
                    log(
                        f"SERVER_SOCKET_RECOVERED client={client_addr[0]}:{client_addr[1]} "
                        f"error={exc!r}"
                    )
                    continue
                last_activity = time.time()
                route_activity[client_addr] = time.time()
                counters["server_rx"] += 1
                counters["server_rx_bytes"] += len(data)
                route_counts = route_counters.get(client_addr)
                if route_counts is not None:
                    route_counts["from_server"] += 1
                    route_counts["from_server_bytes"] += len(data)
                if args.packet_log:
                    log(
                        f"SERVER_RX {addr[0]}:{addr[1]} | client={client_addr[0]}:{client_addr[1]} "
                        f"upstream_port={upstream.getsockname()[1]} | "
                        f"{classify_packet(data)} | {format_packet(data)}"
                    )
                capture_admission_packet(client_addr, "from_server", data)
                capture_route_packet(client_addr, "from_server", data)
                if len(data) >= 7 and data[:3] == b"\x00\x00\x03":
                    original_sequence = struct.unpack_from("<I", data, 3)[0]
                    translations = server_sequence_translation.setdefault(client_addr, {})
                    visible_sequence = translations.get(original_sequence)
                    if visible_sequence is None:
                        offset = server_sequence_offset.get(client_addr, 0)
                        visible_sequence = (original_sequence + offset) & 0xFFFFFFFF
                        translations[original_sequence] = visible_sequence
                        last_server_sequence[client_addr] = visible_sequence
                        server_ack_translation.setdefault(client_addr, {})[visible_sequence] = original_sequence
                    if visible_sequence != original_sequence:
                        data = rewrite_reliable_sequence(data, visible_sequence)
                data = maybe_repair_joiner_picker_packet(client_addr, data)
                team_event = parse_server_team_chat(data)
                if team_event is not None:
                    sender_number, message = team_event
                    receiving_team = route_team.get(client_addr)
                    match = next(
                        (
                            item
                            for item in pending_team_chat
                            if item[1] == message
                            and receiving_team is not None
                            and route_team.get(item[3]) == receiving_team
                        ),
                        None,
                    )
                    if match is not None:
                        team_chat_sender_names[sender_number] = match[2]
                        route_player_number[match[3]] = sender_number
                        pending_team_chat.remove(match)
                    connect = route_connect.get(client_addr)
                    if (
                        args.joiner_team_chat_fallback
                        and connect is not None
                        and connect.match_key
                        and match is not None
                    ):
                        candidates = (
                            joiner_addr
                            for joiner_addr, joiner_connect in tuple(route_connect.items())
                            if not joiner_connect.match_key
                            and joiner_addr in upstream_by_client
                        )
                        for joiner_addr in team_chat_recipient_routes(
                            match[3], route_team, candidates
                        ):
                            inject_visible_team_chat(
                                joiner_addr,
                                sender_number,
                                message,
                                match[2],
                                "host_native_team_echo",
                            )
                    if (
                        args.joiner_team_chat_fallback
                        and connect is not None
                        and not connect.match_key
                    ):
                        visible = make_joiner_team_chat_visible(data)
                        if visible is not None:
                            data = visible
                            log(
                                f"JOINER_TEAM_CHAT_VISIBLE client={client_addr[0]}:{client_addr[1]} "
                                f"sender={sender_number} bytes={len(data)}"
                            )
                special = describe_special_packet(data)
                if special:
                    log(f"SERVER_RX_DETAIL {addr[0]}:{addr[1]} | {special}")
                if len(data) >= 6 and data[:3] == b"\x00\x00\x01":
                    token = data[4:6]
                    pending = pending_browser_queries.pop(token, None)
                    if pending is not None:
                        sent_at = float(pending["sent_at"])
                        client_addr = pending["client_addr"]
                        log(
                            "BROWSER_REPLY "
                            f"token={token.hex()} from={addr[0]}:{addr[1]} "
                            f"to={client_addr[0]}:{client_addr[1]} latency={time.time() - sent_at:.3f}s"
                        )
                sent = client_sock.sendto(data, client_addr)
                counters["client_tx"] += 1
                counters["client_tx_bytes"] += sent
                if args.packet_log:
                    log(f"CLIENT_TX {client_addr[0]}:{client_addr[1]} | forwarded={sent}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print(f"{now_text()} | STOP requested", flush=True)
        raise SystemExit(0)
