from __future__ import annotations

import csv
import io
import os
import subprocess
from pathlib import Path


MODULE_MARKERS = (
    "-m thorgor.master.server",
    "-m thorgor.chat.server",
    "-m thorgor.protocols.game_protocol",
    "-m thorgor.game_manager.dedicated_slave",
    "-m thorgor.game_manager.native_match_id",
    "-m thorgor.game_manager.manager_process",
    "-m thorgor dashboard",
)
LEGACY_MARKERS = (
    "thorgor_hon_sandboxed_masterserver",
    "thorgor_hon_chatserver",
    "hon_udp_shim",
    "hon_manager_status_bridge",
    "hon_native_matchid_bridge",
    "hon_v49_dashboard",
)
FROZEN_SERVICES = {
    "thorgordashboard.exe",
    "thorgormasterserver.exe",
    "thorgorchatserver.exe",
    "thorgorudpshim.exe",
    "thorgormanagerbridge.exe",
    "thorgornativebridge.exe",
}
THORGOR_LISTENERS = {("udp", 11236), ("tcp", 11031), ("tcp", 1135), ("tcp", 1136)}


def _is_thorgor_process(name: str, command: str) -> bool:
    lowered_name = name.casefold()
    lowered = command.casefold()
    if lowered_name == "hon.exe":
        return " -manager" in lowered or " -dedicated" in lowered
    if lowered_name in FROZEN_SERVICES:
        return True
    if lowered_name not in {"python.exe", "pythonw.exe"}:
        return False
    return any(marker in lowered for marker in MODULE_MARKERS + LEGACY_MARKERS)


def discover_processes() -> tuple[tuple[int, str, str], ...]:
    if os.name != "nt":
        return ()
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    result = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine | ConvertTo-Csv -NoTypeInformation",
        ],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Windows process inventory failed")
    rows = []
    for row in csv.DictReader(io.StringIO(result.stdout.lstrip("\ufeff\r\n"))):
        try:
            pid = int(row.get("ProcessId") or 0)
        except ValueError:
            continue
        name = row.get("Name") or ""
        command = row.get("CommandLine") or ""
        if pid and _is_thorgor_process(name, command):
            rows.append((pid, name, command))
    return tuple(rows)


def discover_listener_processes() -> tuple[tuple[int, str, str], ...]:
    """Find stale stack owners even when Windows hides their command lines."""
    if os.name != "nt":
        return ()
    rows: dict[int, tuple[int, str, str]] = {}
    for protocol in ("tcp", "udp"):
        result = subprocess.run(
            ["netstat.exe", "-ano", "-p", protocol],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            columns = line.split()
            if len(columns) < 4 or columns[0].casefold() != protocol:
                continue
            try:
                port = int(columns[1].rsplit(":", 1)[-1])
                pid = int(columns[-1])
            except ValueError:
                continue
            if pid > 0 and (protocol, port) in THORGOR_LISTENERS:
                rows[pid] = (pid, "listener", f"{protocol.upper()} {columns[1]}")
    return tuple(rows.values())


def cleanup_stale_processes(exclude: set[int] | None = None) -> tuple[int, ...]:
    excluded = set(exclude or ()) | {os.getpid()}
    stopped = []
    candidates = {
        pid: (pid, name, command)
        for pid, name, command in (*discover_processes(), *discover_listener_processes())
    }
    for pid, _name, _command in candidates.values():
        if pid in excluded:
            continue
        result = subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "taskkill failed").strip()
            raise RuntimeError(
                f"Could not stop stale ThorGor process {pid} ({_name}): {detail}. "
                "Close the old dashboard or run START_STACK.bat as Administrator."
            )
        stopped.append(pid)
    return tuple(stopped)


def main(argv=None) -> int:
    stopped = cleanup_stale_processes()
    print(f"Stopped {len(stopped)} stale ThorGor process(es).")
    return 0
