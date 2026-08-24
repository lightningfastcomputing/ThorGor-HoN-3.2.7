from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


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
    "Set man_allowCPUs 0",
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


def manager_command(hon_home: Path) -> list[str]:
    hon = hon_home / "hon.exe"
    if not hon.is_file():
        raise FileNotFoundError(f"hon.exe not found: {hon}")
    return [
        str(hon),
        "-manager",
        "-noconfig",
        "-execute",
        ";".join(MANAGER_SETTINGS),
        "-masterserver",
        "127.0.0.1",
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Launch the authentic HoN manager/slave process")
    parser.add_argument("--hon-home", type=Path, required=True)
    args = parser.parse_args(argv)
    home = args.hon_home.expanduser().resolve()
    return subprocess.call(manager_command(home), cwd=home)


if __name__ == "__main__":
    raise SystemExit(main())
