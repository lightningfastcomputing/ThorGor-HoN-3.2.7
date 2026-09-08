"""Master-backed game admission and lobby lifecycle operations."""
from __future__ import annotations

import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .packet_decoding import ConnectC0


def validate_c_conn_response(wire: bytes, expected_cookie: str) -> tuple[bool, str, bool]:
    try:
        cookie_bytes = expected_cookie.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return False, "cookie is not UTF-8", False
    marker = b's:6:"cookie";s:' + str(len(cookie_bytes)).encode("ascii") + b':"' + cookie_bytes + b'";'
    if marker not in wire:
        return False, "response cookie did not match", False
    account = re.search(rb's:10:"account_id";i:([1-9][0-9]*);', wire)
    if account is None:
        return False, "response has no positive integer account_id", False
    game_cookie = re.search(rb's:11:"game_cookie";s:([1-9][0-9]*):"([^"\r\n]+)";', wire)
    if game_cookie is None or int(game_cookie.group(1)) != len(game_cookie.group(2)):
        return False, "response has no valid nonempty game_cookie", False
    decisions = re.findall(rb's:13:"is_match_host";i:([01]);', wire)
    if len(decisions) != 1:
        return False, "response has no unique typed match-host authority", False
    creator = decisions[0] == b"1"
    return True, f"account_id={account.group(1).decode('ascii')} creator={int(creator)}", creator


def _post(master_url: str, fields: dict[str, str], timeout: float) -> bytes:
    request = Request(master_url, data=urlencode(fields).encode("ascii"),
                      headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return response.read(64 * 1024)


def authorize_connect_c0(packet: ConnectC0, master_url: str, timeout: float) -> tuple[bool, str, bool]:
    fields = {"f": "c_conn", "cookie": packet.cookie, "ip": packet.ip or "127.0.0.1"}
    if packet.match_key:
        fields["host_key"] = packet.match_key
    try:
        wire = _post(master_url, fields, timeout)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, f"backend request failed: {exc}", False
    return validate_c_conn_response(wire, packet.cookie)


def activate_host_lobby(packet: ConnectC0, lobby: dict[str, str], master_url: str,
                        timeout: float) -> tuple[bool, str]:
    try:
        wire = _post(master_url, {"f": "host_lobby", "cookie": packet.cookie,
                     "host_key": packet.match_key, "version": packet.version, **lobby}, timeout)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, f"backend request failed: {exc}"
    match = re.search(rb's:8:"match_id";i:([1-9][0-9]*);', wire)
    if match is None:
        return False, "backend did not allocate a positive match_id"
    return True, f"match_id={match.group(1).decode('ascii')}"


def release_host_reservation(packet: ConnectC0, master_url: str, timeout: float) -> tuple[bool, str]:
    try:
        wire = _post(master_url, {"f": "host_release", "cookie": packet.cookie,
                                  "host_key": packet.match_key}, timeout)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, f"backend request failed: {exc}"
    return (True, "released") if b's:7:"success";i:1;' in wire else (
        False, "backend did not release reservation"
    )
