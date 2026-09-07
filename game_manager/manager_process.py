from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from thorgor.game_manager.performance import DEDICATED_CPU_ENV, resolve_dedicated_cpu


MANAGER_SETTINGS = (
    "Set man_masterLogin thorgorhost:",
    "Set man_masterPassword test123",
    "Set man_port 1136",
    "Set man_numSlaveAccounts 1",
    "Set man_idleTarget 1",
    "Set man_startServerPort 11235",
    "Set man_endServerPort 11235",
    "Set man_maxServers 1",
    "Set man_broadcastSlaves true",
    "Set man_autoServersPerCPU 1",
    "Set man_reauthFrequency 30000",
    "Set svr_name ThorGor Public 0 0",
    "Set svr_location USE",
    "Set svr_ip 127.0.0.1",
    "Set svr_port 11234",
    "Set svr_broadcast true",
    "Set svr_chatAddress 127.0.0.1",
    "Set svr_chatPort 11031",
    "Set svr_maxClients 10",
    "Set host_affinity -1",
    "Set upd_checkForUpdates false",
)


def manager_settings(dedicated_cpu: int | None) -> tuple[str, ...]:
    if dedicated_cpu is None:
        return MANAGER_SETTINGS
    return MANAGER_SETTINGS + (f"Set man_allowCPUs {dedicated_cpu}",)


def manager_command(hon_home: Path, dedicated_cpu: int | None = None) -> list[str]:
    hon = hon_home / "hon.exe"
    if not hon.is_file():
        raise FileNotFoundError(f"hon.exe not found: {hon}")
    return [
        str(hon),
        "-manager",
        "-noconfig",
        "-execute",
        ";".join(manager_settings(dedicated_cpu)),
        "-masterserver",
        "127.0.0.1",
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Launch the authentic HoN manager/slave process")
    parser.add_argument("--hon-home", type=Path, required=True)
    parser.add_argument(
        "--dedicated-cpu",
        default=None,
        help=f"Logical CPU reserved for the slave: auto, off, or a number (default: ${DEDICATED_CPU_ENV} or auto)",
    )
    args = parser.parse_args(argv)
    home = args.hon_home.expanduser().resolve()
    dedicated_cpu = resolve_dedicated_cpu(args.dedicated_cpu)
    if dedicated_cpu is None:
        print("Dedicated-server CPU isolation disabled")
    else:
        print(f"Dedicated server reserved on logical CPU {dedicated_cpu}")
    return subprocess.call(manager_command(home, dedicated_cpu), cwd=home)


if __name__ == "__main__":
    raise SystemExit(main())
