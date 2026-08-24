#!/usr/bin/env python3
"""HoN 3.2.7.1 manager-control bridge + public-picker readiness state.

Wiring:
  original slave -> 127.0.0.1:1135 -> this bridge -> 127.0.0.1:1136 -> original manager

What v42 does (stable v39/v41 lineage):
  * The slave's REAL 0x40 association is forwarded unchanged.
  * Until a REAL slave 0x42 status appears, this bridge injects the exact fixed
    3.2.7 manager-status header once per second on the already-associated stream.
  * Initial synthetic state is Sleeping (0).
  * If the ORIGINAL manager sends 0x21 WAKE, the synthetic state becomes Idle (1).
  * Optional legacy v39 diagnostic: after genuine 0x21, send one 0x25 status toggle.
  * Preserved v41 probe: after genuine 0x21, optionally send exactly one 0x26 START GAME
    with original K2 baseline name "Bot Auto Match", options "map:caldavar allowduplicate:true mode:bm", and ints -1/-1.
  * If the slave begins sending a REAL 0x42, synthetic status injection stops.

The 0x25 sender shape is statically recovered from the stock manager. The legacy
CPacket::WriteString wire encoding is inferred here as NUL-terminated narrow text;
there is no live 3.2.7 0x25 capture yet, so the injected frame is logged byte-for-byte.

Observed manager-control stream framing:
  uint16 little-endian payload length + payload.

This is intentionally a diagnostic/control-plane bridge. It does not alter player
UDP traffic and it never fabricates the real initial 0x40 association.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import socketserver
import struct
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
WORK = BASE / 'work'
LOG = WORK / 'manager_status_bridge_v42.log'
EVENTS = WORK / 'manager_status_bridge_v42_events.jsonl'
RUN_ID_PATH = WORK / 'v42_run_id.txt'
CONTROL_FLAG = WORK / 'v42_manager_control.connected'
CAP = WORK / 'manager_status_bridge_v42_captures'
LOCK = threading.Lock()
STATE_PATH = WORK / 'v31_registration_state.json'
STATE_LOCK = threading.RLock()


def read_shared_state() -> dict:
    with STATE_LOCK:
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8-sig'))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}


def update_shared_state(**updates) -> dict:
    with STATE_LOCK:
        state = read_shared_state()
        state.update(updates)
        state['manager_bridge_updated_at'] = datetime.now().isoformat(timespec='seconds')
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Multiple project components touch this shared state file.  Windows can
        # transiently deny os.replace() while another process is reading/replacing
        # it, so use a unique temp file and retry rather than killing the bridge.
        tmp = STATE_PATH.with_name(f"{STATE_PATH.name}.bridge.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        last_exc = None
        for attempt in range(20):
            try:
                tmp.replace(STATE_PATH)
                return state
            except PermissionError as exc:
                last_exc = exc
                time.sleep(0.025 * (attempt + 1))
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise last_exc


STATUS_SLEEPING = 0
STATUS_IDLE = 1


def parse_start_game_match_id(wire: bytes) -> int:
    match = re.search(rb's:8:"match_id";i:([1-9][0-9]*);', wire)
    if match is None:
        raise ValueError('start_game response has no positive integer match_id')
    return int(match.group(1))


def parse_php_string_field(wire: bytes, field: str) -> str:
    field_bytes = field.encode('ascii')
    prefix = b's:' + str(len(field_bytes)).encode('ascii') + b':"' + field_bytes + b'";s:'
    offset = wire.find(prefix)
    if offset < 0:
        raise ValueError(f'response has no typed {field} string')
    value_start = offset + len(prefix)
    length_end = wire.find(b':"', value_start)
    if length_end < 0 or not wire[value_start:length_end].isdigit():
        raise ValueError(f'response has invalid {field} string length')
    length = int(wire[value_start:length_end])
    data_start = length_end + 2
    data_end = data_start + length
    if length <= 0 or data_end + 2 > len(wire) or wire[data_end:data_end + 2] != b'";':
        raise ValueError(f'response has invalid {field} string payload')
    return wire[data_start:data_end].decode('utf-8', errors='strict')


def stamp() -> str:
    return datetime.now().isoformat(timespec='milliseconds').replace('T', ' ')


def ascii_preview(data: bytes) -> str:
    return ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)


def current_run_id() -> str:
    try:
        value = RUN_ID_PATH.read_text(encoding='utf-8-sig').strip()
        return value or 'missing-run-id'
    except OSError:
        return 'missing-run-id'


def event(kind: str, **fields) -> None:
    """Append immutable, machine-readable evidence owned by this bridge."""
    WORK.mkdir(parents=True, exist_ok=True)
    record = {
        'timestamp': datetime.now().isoformat(timespec='milliseconds'),
        'run_id': current_run_id(),
        'source': 'v42_bridge',
        'kind': kind,
        **fields,
    }
    line = json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n'
    with LOCK:
        with EVENTS.open('a', encoding='utf-8') as f:
            f.write(line)


def read_nul_string(payload: bytes, offset: int) -> tuple[str, int]:
    end = payload.find(b'\x00', offset)
    if end < 0:
        raise ValueError(f'missing NUL terminator at offset {offset}')
    return payload[offset:end].decode('utf-8', errors='replace'), end + 1


def decode_start_game(payload: bytes) -> dict:
    if not payload or payload[0] != 0x26:
        raise ValueError('not a 0x26 payload')
    title, off = read_nul_string(payload, 1)
    options, off = read_nul_string(payload, off)
    if len(payload) < off + 8:
        raise ValueError(f'truncated 0x26 integer tail at offset {off}')
    int1, int2 = struct.unpack_from('<ii', payload, off)
    off += 8
    return {
        'opcode': '0x26', 'title': title, 'options': options,
        'int1': int1, 'int2': int2, 'trailing_hex': payload[off:].hex(),
    }


def decode_result(payload: bytes, expected_opcode: int) -> dict:
    """Conservative 0x46/0x47 decoder; unknown bytes always remain visible."""
    if not payload or payload[0] != expected_opcode:
        raise ValueError(f'not a 0x{expected_opcode:02X} payload')
    result = {
        'opcode': f'0x{expected_opcode:02X}',
        'status': payload[1] if len(payload) >= 2 else None,
        'raw_tail_hex': payload[2:].hex() if len(payload) >= 2 else '',
    }
    if len(payload) >= 3:
        try:
            message, off = read_nul_string(payload, 2)
            result['message_candidate'] = message
            result['after_message_hex'] = payload[off:].hex()
        except ValueError:
            pass
    return result


def log(msg: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    line = f'{stamp()} | {msg}'
    with LOCK:
        print(line, flush=True)
        with LOG.open('a', encoding='utf-8') as f:
            f.write(line + '\n')


def capture(conn_id: str, direction: str, data: bytes) -> None:
    CAP.mkdir(parents=True, exist_ok=True)
    obj = {
        'timestamp': stamp(),
        'run_id': current_run_id(),
        'source': 'v42_bridge',
        'connection': conn_id,
        'direction': direction,
        'length': len(data),
        'hex': data.hex(),
        'ascii': ascii_preview(data),
    }
    name = datetime.now().strftime('%Y%m%d_%H%M%S_%f') + f'_{conn_id}_{direction}.json'
    with (CAP / name).open('w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)


def framed(payload: bytes) -> bytes:
    if len(payload) > 0xFFFF:
        raise ValueError('payload too long')
    return struct.pack('<H', len(payload)) + payload


def runtime_console_command_payload(command: str) -> bytes:
    raw = command.encode('ascii', errors='strict')
    if b'\x00' in raw:
        raise ValueError('command contains NUL')
    # Stock manager emits opcode 0x25 then CPacket::WriteString(...).
    # For this diagnostic build, WriteString is encoded as narrow NUL-terminated text.
    return b'\x25' + raw + b'\x00'


def encode_packet_string(text: str, encoding: str) -> bytes:
    """Experimental CPacket::WriteString serializer selector.

    ascii-nul matches the existing v39 hypothesis. Other modes are provided so
    the wire format can be changed from the launcher without another code edit.
    """
    if '\x00' in text:
        raise ValueError('packet string contains NUL')
    if encoding == 'ascii-nul':
        return text.encode('ascii', errors='strict') + b'\x00'
    if encoding == 'utf16le-nul':
        return text.encode('utf-16le') + b'\x00\x00'
    if encoding == 'u16len-ascii':
        raw = text.encode('ascii', errors='strict')
        if len(raw) > 0xFFFF:
            raise ValueError('packet string too long')
        return struct.pack('<H', len(raw)) + raw
    if encoding == 'u16len-utf16le':
        raw = text.encode('utf-16le')
        chars = len(text)
        if chars > 0xFFFF:
            raise ValueError('packet string too long')
        return struct.pack('<H', chars) + raw
    raise ValueError(f'unknown packet string encoding: {encoding}')


def start_game_payload(name: str, options: str, int1: int, int2: int, encoding: str) -> bytes:
    # Recovered stock 0x26 field order:
    # opcode, WriteString(name), WriteString(options), WriteInt(int1), WriteInt(int2)
    return (
        b'\x26'
        + encode_packet_string(name, encoding)
        + encode_packet_string(options, encoding)
        + struct.pack('<ii', int1, int2)
    )


def status_payload(status: int) -> bytes:
    # Exact fixed header consumed by the 3.2.7.1 manager's 0x42 handler:
    # opcode, status, systemTime, cpuLoad, clients, matchStarted,
    # bytesSent, packetsSent, bytesDropped, packetsDropped,
    # bytesReceived, packetsReceived, processMemUsage.
    system_time = int(time.monotonic() * 1000) & 0xFFFFFFFF
    return struct.pack(
        '<BBIIBBIIIIIII',
        0x42,
        status & 0xFF,
        system_time,
        0,      # cpu load
        0,      # clients
        0,      # match started
        0, 0,   # bytes/packets sent
        0, 0,   # bytes/packets dropped
        0, 0,   # bytes/packets received
        0,      # process memory; diagnostic bridge leaves it zero
    )


class BridgeState:
    def __init__(
        self, conn_id: str, upstream: socket.socket, upstream_send_lock: threading.Lock,
        slave: socket.socket, slave_send_lock: threading.Lock, runtime_status_command: bool,
        inject_start_game: bool, start_game_encoding: str, start_game_delay: float,
        master_url: str,
    ):
        self.conn_id = conn_id
        self.upstream = upstream
        self.upstream_send_lock = upstream_send_lock
        self.slave = slave
        self.slave_send_lock = slave_send_lock
        self.runtime_status_command = runtime_status_command
        self.inject_start_game = inject_start_game
        self.start_game_encoding = start_game_encoding
        self.start_game_delay = start_game_delay
        self.master_url = master_url
        self.runtime_status_command_sent = threading.Event()
        self.max_clients_command_sent = threading.Event()
        self.start_game_sent = threading.Event()
        self.stop = threading.Event()
        self.associated = threading.Event()
        self.real_status_seen = threading.Event()
        self.status_lock = threading.Lock()
        self.synthetic_status = STATUS_SLEEPING
        self.inject_thread: threading.Thread | None = None
        self.match_id_thread: threading.Thread | None = None
        self.native_match_id_requested = 0

    def set_status(self, value: int, reason: str) -> None:
        with self.status_lock:
            changed = self.synthetic_status != value
            self.synthetic_status = value
        name = 'Sleeping' if value == STATUS_SLEEPING else 'Idle' if value == STATUS_IDLE else str(value)
        update_shared_state(
            manager_control_connected=True,
            server_status=value,
            lifecycle=name.lower(),
            idle_confirmed=(value == STATUS_IDLE),
            sleeping_confirmed=(value == STATUS_SLEEPING),
            available_confirmed=(value in (STATUS_SLEEPING, STATUS_IDLE)),
            manager_status_source='v42_bridge_synthetic',
            manager_status_reason=reason,
        )
        if changed:
            log(f'BRIDGE_STATE {self.conn_id} synthetic_status={name}({value}) reason={reason}')

    def mark_real_status(self, payload: bytes) -> None:
        first = not self.real_status_seen.is_set()
        self.real_status_seen.set()
        status = payload[1] if len(payload) >= 2 else None
        if status is not None:
            name = 'sleeping' if status == STATUS_SLEEPING else 'idle' if status == STATUS_IDLE else f'status_{status}'
            update_shared_state(
                manager_control_connected=True,
                server_status=status,
                lifecycle=name,
                idle_confirmed=(status == STATUS_IDLE),
                sleeping_confirmed=(status == STATUS_SLEEPING),
                available_confirmed=(status in (STATUS_SLEEPING, STATUS_IDLE)),
                manager_status_source='real_slave_0x42',
            )
        if first:
            log(f'REAL_STATUS_TAKES_OVER {self.conn_id} opcode=0x42 status={status}; synthetic injection disabled')

    def inject_runtime_status_toggle(self) -> None:
        if not self.runtime_status_command:
            log(f'RUNTIME_STATUS_COMMAND_DISABLED {self.conn_id}')
            return
        if self.runtime_status_command_sent.is_set():
            return
        if self.real_status_seen.is_set():
            log(f'RUNTIME_STATUS_COMMAND_SKIPPED {self.conn_id} reason=real_0x42_already_seen')
            return
        if not self.associated.is_set():
            log(f'RUNTIME_STATUS_COMMAND_SKIPPED {self.conn_id} reason=no_real_0x40_association')
            return

        command = 'Set svr_sendStatusToManager 1'
        payload = runtime_console_command_payload(command)
        packet = framed(payload)
        # Mark before send so duplicate wakes cannot enqueue a second command.
        self.runtime_status_command_sent.set()
        try:
            with self.slave_send_lock:
                self.slave.sendall(packet)
            update_shared_state(
                runtime_status_command_injected=True,
                runtime_status_command=command,
                runtime_status_command_opcode='0x25',
                runtime_status_command_payload_hex=payload.hex(),
                runtime_status_command_encoding='inferred_narrow_nul_terminated_WriteString',
            )
            log(
                f'RUNTIME_STATUS_COMMAND_INJECTED {self.conn_id} opcode=0x25 '
                f'command={command!r} payload_len={len(payload)} hex={payload.hex()}'
            )
            capture(self.conn_id, 'BRIDGE_TO_SLAVE_RUNTIME_0X25', packet)
        except OSError as e:
            update_shared_state(runtime_status_command_injected=False, runtime_status_command_error=repr(e))
            log(f'RUNTIME_STATUS_COMMAND_ERROR {self.conn_id} {e!r}')

    def inject_max_clients(self) -> None:
        if self.max_clients_command_sent.is_set():
            return
        command = 'Set svr_maxClients 10'
        payload = runtime_console_command_payload(command)
        packet = framed(payload)
        self.max_clients_command_sent.set()
        try:
            with self.slave_send_lock:
                self.slave.sendall(packet)
            update_shared_state(
                native_max_clients_injected=True,
                native_max_clients=10,
                native_max_clients_opcode='0x25',
                native_max_clients_command=command,
                native_max_clients_payload_hex=payload.hex(),
            )
            log(
                f'NATIVE_MAX_CLIENTS_INJECTED {self.conn_id} opcode=0x25 '
                f'command={command!r} hex={payload.hex()}'
            )
            capture(self.conn_id, 'BRIDGE_TO_SLAVE_MAX_CLIENTS_0X25', packet)
        except OSError as exc:
            update_shared_state(
                native_max_clients_injected=False,
                native_max_clients_error=repr(exc),
            )
            log(f'NATIVE_MAX_CLIENTS_ERROR {self.conn_id} {exc!r}')

    def inject_start_game_probe(self) -> None:
        if not self.inject_start_game:
            return
        if self.start_game_sent.is_set():
            return
        if not self.associated.is_set():
            log(f'START_GAME_PROBE_SKIPPED {self.conn_id} reason=no_real_0x40_association')
            return

        # Give the stock slave a short interval to process the genuine 0x21 WAKE.
        if self.stop.wait(self.start_game_delay):
            return
        if self.start_game_sent.is_set():
            return

        name = 'Bot Auto Match'
        options = 'map:caldavar allowduplicate:true mode:bm'
        shared = read_shared_state()
        session = str(shared.get('server_session', ''))
        if not session:
            bootstrap_body = urlencode({
                'f': 'new_session', 'ip': '127.0.0.1', 'port': '11235',
                'name': 'ThorGor Public',
            }).encode('ascii')
            bootstrap_request = Request(
                self.master_url, data=bootstrap_body,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST',
            )
            try:
                with urlopen(bootstrap_request, timeout=3.0) as response:
                    session = parse_php_string_field(response.read(64 * 1024), 'session')
                update_shared_state(legacy_session_bootstrapped=True, server_session=session)
                log(f'LEGACY_SESSION_BOOTSTRAPPED {self.conn_id} session_len={len(session)}')
            except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, ValueError) as e:
                update_shared_state(start_game_probe_injected=False, start_game_probe_error=repr(e))
                log(f'START_GAME_SESSION_ERROR {self.conn_id} {e!r}')
                return
        body = urlencode({
            'f': 'start_game', 'session': session, 'map': 'caldavar',
            'version': '3.2.7.1', 'mname': name,
        }).encode('ascii')
        request = Request(
            self.master_url, data=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST',
        )
        try:
            with urlopen(request, timeout=3.0) as response:
                match_id = parse_start_game_match_id(response.read(64 * 1024))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as e:
            update_shared_state(start_game_probe_injected=False, start_game_probe_error=repr(e))
            log(f'START_GAME_BACKEND_ERROR {self.conn_id} {e!r}')
            return

        payload = start_game_payload(name, options, -1, -1, self.start_game_encoding)
        packet = framed(payload)
        self.start_game_sent.set()
        try:
            with self.slave_send_lock:
                self.slave.sendall(packet)
            update_shared_state(
                start_game_probe_injected=True,
                start_game_probe_opcode='0x26',
                start_game_probe_name=name,
                start_game_probe_options=options,
                start_game_probe_int1=-1,
                start_game_probe_int2=-1,
                start_game_probe_encoding=self.start_game_encoding,
                start_game_probe_payload_hex=payload.hex(),
                backend_start_game_allocated=True,
                match_id=match_id,
            )
            log(
                f'START_GAME_PROBE_INJECTED {self.conn_id} opcode=0x26 '
                f'name={name!r} options={options!r} ints=(-1,-1) '
                f'encoding={self.start_game_encoding} payload_len={len(payload)} hex={payload.hex()}'
            )
            log(f'START_GAME_BACKEND_ALLOCATED {self.conn_id} match_id={match_id}')
            event(
                'injected_start_game', connection=self.conn_id, opcode='0x26',
                decoded=decode_start_game(payload), payload_hex=payload.hex(),
            )
            capture(self.conn_id, 'BRIDGE_TO_SLAVE_STARTGAME_0X26', packet)
        except OSError as e:
            update_shared_state(start_game_probe_injected=False, start_game_probe_error=repr(e))
            log(f'START_GAME_PROBE_ERROR {self.conn_id} {e!r}')

    def watch_for_native_match_id_request(self) -> None:
        """Start the reserved match through the stock manager command path.

        host_lobby is published before the shim forwards the client's final
        Create Game packet. Opcode 0x26 makes CHostServer::StartGame construct
        the native match state.
        """
        pending_id = 0
        pending_since = 0.0
        while not self.stop.is_set():
            shared = read_shared_state()
            try:
                match_id = int(shared.get('match_id', 0) or 0)
            except (TypeError, ValueError):
                match_id = 0
            if match_id <= 0:
                pending_id = 0
                pending_since = 0.0
                self.native_match_id_requested = 0
            elif match_id != self.native_match_id_requested:
                if pending_id != match_id:
                    pending_id = match_id
                    pending_since = time.monotonic()
                elif time.monotonic() - pending_since >= 0.05:
                    name = str(shared.get('match_name') or 'Unnamed Game')
                    options = str(shared.get('match_options') or 'map:caldavar teamsize:5')
                    payload = start_game_payload(name, options, -1, -1, self.start_game_encoding)
                    packet = framed(payload)
                    try:
                        with self.slave_send_lock:
                            self.slave.sendall(packet)
                        self.native_match_id_requested = match_id
                        update_shared_state(
                            native_start_game_injected=True,
                            native_start_game_injected_for=match_id,
                            native_start_game_opcode='0x26',
                            native_start_game_name=name,
                            native_start_game_options=options,
                            native_start_game_int1=-1,
                            native_start_game_int2=-1,
                            native_start_game_encoding=self.start_game_encoding,
                            native_start_game_payload_hex=payload.hex(),
                        )
                        log(
                            f'NATIVE_START_GAME_INJECTED {self.conn_id} '
                            f'match_id={match_id} opcode=0x26 name={name!r} '
                            f'options={options!r} ints=(-1,-1) '
                            f'encoding={self.start_game_encoding} hex={payload.hex()}'
                        )
                        event('native_start_game', connection=self.conn_id, match_id=match_id,
                              decoded=decode_start_game(payload), payload_hex=payload.hex())
                        capture(self.conn_id, 'BRIDGE_TO_SLAVE_NATIVE_STARTGAME_0X26', packet)
                    except OSError as exc:
                        update_shared_state(
                            native_start_game_injected=False,
                            native_start_game_error=repr(exc),
                        )
                        log(f'NATIVE_START_GAME_ERROR {self.conn_id} {exc!r}')
                        return
            if self.stop.wait(0.25):
                return

    def start_after_association(self) -> None:
        if self.associated.is_set():
            return
        self.associated.set()
        update_shared_state(
            manager_control_connected=True,
            manager_associated=True,
            manager_association_opcode='0x40',
            manager_association_real=True,
            manager_status_source='v42_bridge_synthetic',
            server_status=STATUS_SLEEPING,
            lifecycle='sleeping',
            sleeping_confirmed=True,
            idle_confirmed=False,
            available_confirmed=True,
        )
        log(f'BRIDGE_ARMED {self.conn_id} real 0x40 association observed; synthetic Sleeping status will begin')
        self.inject_thread = threading.Thread(target=self._inject_loop, daemon=True)
        self.inject_thread.start()
        self.match_id_thread = threading.Thread(
            target=self.watch_for_native_match_id_request, daemon=True
        )
        self.match_id_thread.start()
        self.inject_max_clients()

    def _inject_loop(self) -> None:
        # Preserve stream order: give the manager a moment to finish processing the real 0x40.
        if self.stop.wait(0.20):
            return
        while not self.stop.is_set() and not self.real_status_seen.is_set():
            with self.status_lock:
                status = self.synthetic_status
            # Refresh shared readiness on every heartbeat. The master and chat
            # are separate processes that also update this JSON file, so this
            # makes the live manager-control proof resilient to a concurrent
            # read/modify/write from either service.
            name = 'Sleeping' if status == STATUS_SLEEPING else 'Idle' if status == STATUS_IDLE else str(status)
            update_shared_state(
                manager_control_connected=True, manager_associated=True,
                server_status=status, lifecycle=name.lower(),
                idle_confirmed=(status == STATUS_IDLE), sleeping_confirmed=(status == STATUS_SLEEPING),
                available_confirmed=(status in (STATUS_SLEEPING, STATUS_IDLE)),
                manager_status_source='v42_bridge_synthetic'
            )
            payload = status_payload(status)
            packet = framed(payload)
            try:
                with self.upstream_send_lock:
                    self.upstream.sendall(packet)
                log(
                    f'BRIDGE_TO_MANAGER_FRAME {self.conn_id} payload_len={len(payload)} '
                    f'opcode=0x42 status={name}({status}) hex={payload.hex()}'
                )
                capture(self.conn_id, 'BRIDGE_TO_MANAGER', packet)
            except OSError as e:
                log(f'BRIDGE_INJECT_ERROR {self.conn_id} {e!r}')
                return
            if self.stop.wait(1.0):
                return


class FrameDecoder:
    def __init__(self, direction: str, conn_id: str, state: BridgeState):
        self.direction = direction
        self.conn_id = conn_id
        self.state = state
        self.buf = bytearray()

    def feed(self, data: bytes) -> None:
        self.buf.extend(data)
        while len(self.buf) >= 2:
            n = int.from_bytes(self.buf[:2], 'little')
            if n > 65500:
                log(f'{self.direction}_FRAME_BADLEN {self.conn_id} declared={n} buffered={len(self.buf)}')
                self.buf.clear()
                return
            if len(self.buf) < 2 + n:
                return
            payload = bytes(self.buf[2:2+n])
            del self.buf[:2+n]
            op = payload[0] if payload else None
            op_text = f'0x{op:02X}' if op is not None else 'none'
            log(
                f'{self.direction}_FRAME {self.conn_id} payload_len={n} '
                f'opcode={op_text} hex={payload.hex()} ascii={ascii_preview(payload)}'
            )
            event(
                'control_frame', connection=self.conn_id, direction=self.direction,
                payload_length=n, opcode=op_text, payload_hex=payload.hex(),
            )

            if self.direction == 'SLAVE_TO_MANAGER':
                if op == 0x40:
                    event('real_slave_association', connection=self.conn_id, payload_hex=payload.hex())
                    self.state.start_after_association()
                elif op == 0x42:
                    event(
                        'real_slave_status', connection=self.conn_id,
                        status=payload[1] if len(payload) >= 2 else None,
                        payload_hex=payload.hex(),
                    )
                    self.state.mark_real_status(payload)
                elif op == 0x46:
                    decoded = decode_result(payload, 0x46)
                    update_shared_state(slave_start_game_result_seen=True, slave_start_game_result_payload_hex=payload.hex())
                    log(
                        f'REAL_SLAVE_START_GAME_RESULT {self.conn_id} opcode=0x46 '
                        f'payload_len={len(payload)} decoded={json.dumps(decoded, sort_keys=True)} hex={payload.hex()}'
                    )
                    event('real_slave_start_game_result', connection=self.conn_id, decoded=decoded, payload_hex=payload.hex())
                elif op == 0x47:
                    decoded = decode_result(payload, 0x47)
                    update_shared_state(slave_client_auth_result_seen=True, slave_client_auth_result_payload_hex=payload.hex())
                    log(
                        f'REAL_SLAVE_CLIENT_AUTH_RESULT {self.conn_id} opcode=0x47 '
                        f'payload_len={len(payload)} decoded={json.dumps(decoded, sort_keys=True)} hex={payload.hex()}'
                    )
                    event('real_slave_client_auth_result', connection=self.conn_id, decoded=decoded, payload_hex=payload.hex())
            elif self.direction == 'MANAGER_TO_SLAVE':
                if op == 0x21:
                    log(f'GENUINE_MANAGER_WAKE {self.conn_id} opcode=0x21')
                    event('genuine_manager_wake', connection=self.conn_id, payload_hex=payload.hex())
                    self.state.set_status(STATUS_IDLE, 'original manager sent genuine 0x21 WAKE')
                    self.state.inject_runtime_status_toggle()
                    if self.state.inject_start_game:
                        threading.Thread(target=self.state.inject_start_game_probe, daemon=True).start()
                elif op == 0x20:
                    log(f'GENUINE_MANAGER_SLEEP {self.conn_id} opcode=0x20')
                    self.state.set_status(STATUS_SLEEPING, 'original manager sent genuine 0x20 SLEEP')
                elif op == 0x26:
                    try:
                        decoded = decode_start_game(payload)
                    except ValueError as exc:
                        decoded = {'decode_error': str(exc), 'payload_hex': payload.hex()}
                    update_shared_state(manager_start_game_seen=True, manager_start_game_payload_hex=payload.hex())
                    log(
                        f'GENUINE_MANAGER_START_GAME {self.conn_id} opcode=0x26 '
                        f'payload_len={len(payload)} decoded={json.dumps(decoded, sort_keys=True)} hex={payload.hex()}'
                    )
                    event('genuine_manager_start_game', connection=self.conn_id, decoded=decoded, payload_hex=payload.hex())


class Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        cid = f'{self.client_address[0]}_{self.client_address[1]}'
        log(f'ACCEPT {cid} -> {self.server.target_host}:{self.server.target_port}')
        upstream = None
        last = None
        for _ in range(100):
            try:
                upstream = socket.create_connection(
                    (self.server.target_host, self.server.target_port), timeout=1.0
                )
                break
            except OSError as e:
                last = e
                time.sleep(0.1)
        if upstream is None:
            log(f'UPSTREAM_CONNECT_FAILED {cid} error={last!r}')
            return

        CONTROL_FLAG.parent.mkdir(parents=True, exist_ok=True)
        CONTROL_FLAG.write_text(f'{stamp()} {cid}\n', encoding='utf-8')
        update_shared_state(manager_control_connected=True, manager_control_peer=cid)
        log(f'CONTROL_CONNECTED {cid} flag={CONTROL_FLAG.name}')

        self.request.settimeout(None)
        upstream.settimeout(None)
        stop = threading.Event()
        upstream_send_lock = threading.Lock()
        slave_send_lock = threading.Lock()
        bridge = BridgeState(
            cid, upstream, upstream_send_lock, self.request, slave_send_lock,
            self.server.runtime_status_command, self.server.inject_start_game,
            self.server.start_game_encoding, self.server.start_game_delay,
            self.server.master_url,
        )
        decoders = {
            'SLAVE_TO_MANAGER': FrameDecoder('SLAVE_TO_MANAGER', cid, bridge),
            'MANAGER_TO_SLAVE': FrameDecoder('MANAGER_TO_SLAVE', cid, bridge),
        }

        def pump(src: socket.socket, dst: socket.socket, direction: str, send_lock: threading.Lock) -> None:
            try:
                while not stop.is_set():
                    data = src.recv(65535)
                    if not data:
                        log(f'{direction}_EOF {cid}')
                        break
                    log(f'{direction} {cid} len={len(data)} hex={data.hex()} ascii={ascii_preview(data)}')
                    capture(cid, direction, data)
                    # Forward real bytes first. Decoder callbacks may then inject follow-up frames.
                    with send_lock:
                        dst.sendall(data)
                    decoders[direction].feed(data)
            except OSError as e:
                log(f'{direction}_ERROR {cid} {e!r}')
            finally:
                stop.set()
                bridge.stop.set()
                try:
                    dst.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        a = threading.Thread(
            target=pump,
            args=(self.request, upstream, 'SLAVE_TO_MANAGER', upstream_send_lock),
            daemon=True,
        )
        b = threading.Thread(
            target=pump,
            args=(upstream, self.request, 'MANAGER_TO_SLAVE', slave_send_lock),
            daemon=True,
        )
        a.start()
        b.start()
        a.join()
        b.join()
        bridge.stop.set()
        upstream.close()
        try:
            CONTROL_FLAG.unlink()
        except FileNotFoundError:
            pass
        update_shared_state(manager_control_connected=False, manager_control_peer='', available_confirmed=False)
        log(f'CLOSE {cid}; CONTROL_DISCONNECTED')


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self, addr, handler, target_host: str, target_port: int, runtime_status_command: bool,
        inject_start_game: bool, start_game_encoding: str, start_game_delay: float,
        master_url: str,
    ):
        self.target_host = target_host
        self.target_port = target_port
        self.runtime_status_command = runtime_status_command
        self.inject_start_game = inject_start_game
        self.start_game_encoding = start_game_encoding
        self.start_game_delay = start_game_delay
        self.master_url = master_url
        super().__init__(addr, handler)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--listen-host', default='0.0.0.0')
    ap.add_argument('--listen-port', type=int, default=1135)
    ap.add_argument('--target-host', default='127.0.0.1')
    ap.add_argument('--target-port', type=int, default=1136)
    ap.add_argument('--master-url', default='http://127.0.0.1/server_requester.php')
    ap.add_argument(
        '--inject-status-toggle-after-wake', action='store_true',
        help='after genuine 0x21, inject one 0x25 command: Set svr_sendStatusToManager 1',
    )
    ap.add_argument(
        '--inject-start-game-after-wake', action='store_true',
        help='after genuine 0x21, inject one experimental 0x26 START GAME probe',
    )
    ap.add_argument(
        '--start-game-string-encoding',
        choices=('ascii-nul', 'utf16le-nul', 'u16len-ascii', 'u16len-utf16le'),
        default='ascii-nul',
        help='experimental CPacket::WriteString wire encoding for the 0x26 probe',
    )
    ap.add_argument(
        '--start-game-delay', type=float, default=0.35,
        help='seconds to wait after genuine 0x21 before sending the 0x26 probe',
    )
    a = ap.parse_args()
    update_shared_state(
        manager_control_connected=False, manager_associated=False,
        manager_start_game_seen=False, slave_start_game_result_seen=False,
        slave_client_auth_result_seen=False,
        runtime_status_command_injected=False, runtime_status_command='',
        start_game_probe_injected=False, start_game_probe_encoding=a.start_game_string_encoding,
        available_confirmed=False, manager_status_source='none'
    )
    log(
        f'PROCESS_START listen={a.listen_host}:{a.listen_port} '
        f'target={a.target_host}:{a.target_port} mode=v42_evidence_baseline run_id={current_run_id()} '
        f'runtime_status_command={a.inject_status_toggle_after_wake} '
        f'start_game_probe={a.inject_start_game_after_wake} '
        f'start_game_encoding={a.start_game_string_encoding} delay={a.start_game_delay} '
        f'master_url={a.master_url!r}'
    )
    event(
        'process_start', listen_host=a.listen_host, listen_port=a.listen_port,
        target_host=a.target_host, target_port=a.target_port,
        inject_status_toggle=a.inject_status_toggle_after_wake,
        inject_start_game=a.inject_start_game_after_wake,
        start_game_encoding=a.start_game_string_encoding,
        start_game_delay=a.start_game_delay,
    )
    with Server(
        (a.listen_host, a.listen_port), Handler, a.target_host, a.target_port,
        a.inject_status_toggle_after_wake, a.inject_start_game_after_wake,
        a.start_game_string_encoding, a.start_game_delay, a.master_url,
    ) as s:
        s.serve_forever(0.1)


if __name__ == '__main__':
    main()
