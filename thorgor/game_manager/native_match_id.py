#!/usr/bin/env python3
"""ThorGor HoN 3.2.7.1 native Match-ID synchronizer (v47).

Purpose
-------
The sandbox backend allocates a positive match_id when the host's final Create Game
packet is observed, but stock game.dll leaves CGameInfo::m_uiMatchID at 0xFFFFFFFF.
This helper mirrors the backend's allocated match_id into the *dedicated* hon.exe's
live CGameInfo object.

The pointer chain was verified against the exact 3.2.7.1 game.dll used by ThorGor:

    game.dll + 0x9163C -> CGame singleton
    CGame + 0x78       -> CGameInfo*
    CGameInfo + 0x84   -> m_uiMatchID

Static proof in stock game.dll:
    RequestMatchID path calls the CGame singleton and executes
    mov edi,[edi+78h]
    mov dword ptr [edi+84h],FFFFFFFFh

Runtime proof (2026-08-09): manually replacing that DWORD with backend match 21
made GetMatchID return 21 and the host lobby display "Match ID: 21".

Safety
------
* Only hon.exe processes whose command line contains -dedicated are considered.
* The helper discovers game.dll from the running -dedicated process, then verifies
  that loaded module's on-disk SHA-256 unless --allow-unknown-game-dll is supplied.
* By default, memory is changed only when the native field is 0 or 0xFFFFFFFF.
  A different positive native ID is never overwritten automatically.
* The desired value must be a positive 32-bit match_id present in the sandbox
  shared-state JSON.

This is intentionally a narrow synchronization shim, not a general memory patcher.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

from thorgor.paths import ROOT


BASE = ROOT
DEFAULT_SHARED_STATE = BASE / "work" / "v31_registration_state.json"
DEFAULT_STATUS = BASE / "work" / "native_matchid_bridge_v47_state.json"
DEFAULT_LOG = BASE / "work" / "native_matchid_bridge_v47.log"

VERIFIED_GAME_DLL_SHA256 = "D345F8537ED9FD5C6705F8F1A9FA6663C5F4AE4476CD328B2D8F1074C044CF99"
GAME_SINGLETON_PTR_RVA = 0x9163C
CGAME_GAMEINFO_OFFSET = 0x78
CGAMEINFO_MATCHID_OFFSET = 0x84
SENTINELS = {0x00000000, 0xFFFFFFFF}


def stamp() -> str:
    return datetime.now().isoformat(timespec="milliseconds").replace("T", " ")


def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{stamp()} | {message}"
    print(line, flush=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.native.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    last_exc = None
    for attempt in range(20):
        try:
            tmp.replace(path)
            return
        except PermissionError as exc:
            last_exc = exc
            time.sleep(0.025 * (attempt + 1))
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass
    raise last_exc


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def desired_match_id(path: Path) -> int | None:
    state = read_json(path)
    try:
        value = int(state.get("match_id", 0))
    except (TypeError, ValueError):
        return None
    if 0 < value <= 0xFFFFFFFE:
        return value
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def dedicated_hon_pids() -> list[int]:
    """Return PIDs for hon.exe command lines containing the -dedicated switch."""
    if os.name != "nt":
        return []
    command = (
        "$ErrorActionPreference='SilentlyContinue';"
        "Get-CimInstance Win32_Process -Filter \"Name='hon.exe'\" | "
        "Where-Object { $_.CommandLine -match '(?i)(^|\\s)-dedicated(\\s|$)' } | "
        "ForEach-Object { $_.ProcessId }"
    )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        timeout=4.0,
        creationflags=creationflags,
        check=False,
    )
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return sorted(set(pids))


if os.name == "nt":
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_OPERATION = 0x0008
    PROCESS_VM_READ = 0x0010
    PROCESS_VM_WRITE = 0x0020
    TH32CS_SNAPMODULE = 0x00000008
    TH32CS_SNAPMODULE32 = 0x00000010
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class MODULEENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("th32ModuleID", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("GlblcntUsage", wintypes.DWORD),
            ("ProccntUsage", wintypes.DWORD),
            ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
            ("modBaseSize", wintypes.DWORD),
            ("hModule", wintypes.HMODULE),
            ("szModule", wintypes.WCHAR * 256),
            ("szExePath", wintypes.WCHAR * 260),
        ]

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.ReadProcessMemory.argtypes = [
        wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.ReadProcessMemory.restype = wintypes.BOOL
    kernel32.WriteProcessMemory.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID, ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.WriteProcessMemory.restype = wintypes.BOOL
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
    kernel32.Module32FirstW.restype = wintypes.BOOL
    kernel32.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
    kernel32.Module32NextW.restype = wintypes.BOOL


def win_error(prefix: str) -> OSError:
    code = ctypes.get_last_error()
    return OSError(code, f"{prefix}: {ctypes.FormatError(code).strip()}")


def module_info(pid: int, module_name: str) -> tuple[int, Path] | None:
    flags = TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32
    snapshot = kernel32.CreateToolhelp32Snapshot(flags, pid)
    if snapshot == INVALID_HANDLE_VALUE:
        return None
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel32.Module32FirstW(snapshot, ctypes.byref(entry)):
            return None
        wanted = module_name.casefold()
        while True:
            if entry.szModule.casefold() == wanted:
                base = ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value
                return base, Path(entry.szExePath)
            if not kernel32.Module32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return None


def module_base(pid: int, module_name: str) -> int | None:
    info = module_info(pid, module_name)
    return info[0] if info else None


class RemoteProcess:
    def __init__(self, pid: int):
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE
        self.pid = pid
        self.handle = kernel32.OpenProcess(access, False, pid)
        if not self.handle:
            raise win_error(f"OpenProcess({pid}) failed")

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> "RemoteProcess":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def read_u32(self, address: int) -> int:
        value = ctypes.c_uint32()
        got = ctypes.c_size_t()
        if not kernel32.ReadProcessMemory(
            self.handle, ctypes.c_void_p(address), ctypes.byref(value), 4, ctypes.byref(got)
        ) or got.value != 4:
            raise win_error(f"ReadProcessMemory(pid={self.pid}, address=0x{address:08X}) failed")
        return int(value.value)

    def write_u32(self, address: int, value: int) -> None:
        data = ctypes.c_uint32(value & 0xFFFFFFFF)
        wrote = ctypes.c_size_t()
        if not kernel32.WriteProcessMemory(
            self.handle, ctypes.c_void_p(address), ctypes.byref(data), 4, ctypes.byref(wrote)
        ) or wrote.value != 4:
            raise win_error(f"WriteProcessMemory(pid={self.pid}, address=0x{address:08X}) failed")


def plausible_32bit_pointer(value: int) -> bool:
    return 0x00010000 <= value < 0x80000000


def inspect_native_match_id(pid: int) -> dict:
    mod = module_info(pid, "game.dll")
    if not mod:
        raise RuntimeError("game.dll is not loaded")
    base, dll_path = mod
    with RemoteProcess(pid) as proc:
        singleton_slot = base + GAME_SINGLETON_PTR_RVA
        game = proc.read_u32(singleton_slot)
        if not plausible_32bit_pointer(game):
            raise RuntimeError(f"CGame singleton is not ready (0x{game:08X})")
        game_info = proc.read_u32(game + CGAME_GAMEINFO_OFFSET)
        if not plausible_32bit_pointer(game_info):
            raise RuntimeError(f"CGameInfo is not ready (0x{game_info:08X})")
        field = game_info + CGAMEINFO_MATCHID_OFFSET
        match_id = proc.read_u32(field)
    return {
        "pid": pid,
        "game_dll_base": base,
        "game_dll_path": str(dll_path),
        "cgame": game,
        "cgameinfo": game_info,
        "match_id_address": field,
        "native_match_id": match_id,
    }


def synchronize_pid(pid: int, wanted: int, allow_overwrite_positive: bool = False) -> tuple[str, dict]:
    info = inspect_native_match_id(pid)
    current = info["native_match_id"]
    if current == wanted:
        return "already_synced", info
    if current not in SENTINELS and not allow_overwrite_positive:
        return "positive_mismatch_refused", info

    with RemoteProcess(pid) as proc:
        proc.write_u32(info["match_id_address"], wanted)
        confirmed = proc.read_u32(info["match_id_address"])
    info["written_match_id"] = wanted
    info["confirmed_match_id"] = confirmed
    if confirmed != wanted:
        return "verification_failed", info
    return "written", info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Synchronize backend match_id into dedicated HoN CGameInfo")
    ap.add_argument("--state-file", type=Path, default=DEFAULT_SHARED_STATE)
    ap.add_argument("--status-file", type=Path, default=DEFAULT_STATUS)
    ap.add_argument("--log-file", type=Path, default=DEFAULT_LOG)
    ap.add_argument("--poll", type=float, default=0.25)
    ap.add_argument("--allow-unknown-game-dll", action="store_true")
    ap.add_argument("--force-positive-overwrite", action="store_true")
    ap.add_argument("--once", action="store_true", help="perform one scan and exit")
    args = ap.parse_args(argv)

    if os.name != "nt":
        print("This helper must run on Windows against the 32-bit HoN dedicated process.", file=sys.stderr)
        return 2

    append_log(
        args.log_file,
        f"PROCESS_START state={str(args.state_file)!r} poll={args.poll:.3f}s "
        f"pointer_chain=game.dll+0x{GAME_SINGLETON_PTR_RVA:X}->+0x{CGAME_GAMEINFO_OFFSET:X}->+0x{CGAMEINFO_MATCHID_OFFSET:X} "
        f"dll_verification=loaded-module-path",
    )

    verified_modules: dict[tuple[int, str], str] = {}
    last_signature = None
    while True:
        wanted = desired_match_id(args.state_file)
        pids = dedicated_hon_pids()
        status = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "desired_match_id": wanted,
            "dedicated_pids": pids,
            "results": [],
        }

        if wanted is not None:
            for pid in pids:
                try:
                    mod = module_info(pid, "game.dll")
                    if not mod:
                        raise RuntimeError("game.dll is not loaded")
                    _base, dll_path = mod
                    key = (pid, str(dll_path).casefold())
                    dll_hash = verified_modules.get(key)
                    if dll_hash is None:
                        dll_hash = sha256_file(dll_path)
                        if dll_hash != VERIFIED_GAME_DLL_SHA256 and not args.allow_unknown_game_dll:
                            raise RuntimeError(
                                f"loaded game.dll hash mismatch path={str(dll_path)!r} "
                                f"sha256={dll_hash} expected={VERIFIED_GAME_DLL_SHA256}"
                            )
                        verified_modules[key] = dll_hash
                        append_log(
                            args.log_file,
                            f"GAME_DLL_VERIFIED pid={pid} path={str(dll_path)!r} sha256={dll_hash}",
                        )
                    action, info = synchronize_pid(pid, wanted, args.force_positive_overwrite)
                    info["game_dll_sha256"] = dll_hash
                    result = {"action": action, **info}
                    status["results"].append(result)
                    signature = (pid, wanted, action, info.get("native_match_id"), info.get("confirmed_match_id"))
                    if signature != last_signature:
                        if action == "written":
                            append_log(
                                args.log_file,
                                f"NATIVE_MATCH_ID_WRITTEN pid={pid} desired={wanted} "
                                f"game=0x{info['cgame']:08X} cgameinfo=0x{info['cgameinfo']:08X} "
                                f"field=0x{info['match_id_address']:08X} prior=0x{info['native_match_id']:08X} "
                                f"confirmed={info['confirmed_match_id']}",
                            )
                        elif action == "positive_mismatch_refused":
                            append_log(
                                args.log_file,
                                f"NATIVE_MATCH_ID_REFUSED pid={pid} desired={wanted} "
                                f"native={info['native_match_id']} reason=positive_mismatch",
                            )
                        elif action == "verification_failed":
                            append_log(args.log_file, f"NATIVE_MATCH_ID_VERIFY_FAILED pid={pid} desired={wanted}")
                        last_signature = signature
                except Exception as exc:
                    status["results"].append({"pid": pid, "action": "error", "error": repr(exc)})
                    signature = (pid, wanted, "error", repr(exc))
                    if signature != last_signature:
                        append_log(args.log_file, f"NATIVE_MATCH_ID_WAIT pid={pid} desired={wanted} error={exc}")
                        last_signature = signature

        atomic_json_write(args.status_file, status)
        if args.once:
            return 0
        time.sleep(max(0.05, args.poll))


if __name__ == "__main__":
    raise SystemExit(main())
