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


def cleanup_stale_processes(exclude: set[int] | None = None) -> tuple[int, ...]:
    excluded = set(exclude or ()) | {os.getpid()}
    stopped = []
    for pid, _name, _command in discover_processes():
        if pid in excluded:
            continue
        subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        stopped.append(pid)
    return tuple(stopped)


def main(argv=None) -> int:
    stopped = cleanup_stale_processes()
    print(f"Stopped {len(stopped)} stale ThorGor process(es).")
    return 0
