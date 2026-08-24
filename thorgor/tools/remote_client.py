from __future__ import annotations

import argparse
import ipaddress
import os
import re
import socket
import subprocess
import traceback
from pathlib import Path

from thorgor.paths import ROOT
from thorgor.patches.installer import install_supported_patches


CHAT_HOSTNAME = "chatserver.heroesofnewerth.com"
SETUP_LOG = ROOT / "remote_client_setup.log"


def ipv4(value: str) -> str:
    address = ipaddress.ip_address(value)
    if address.version != 4 or address.is_unspecified:
        raise ValueError(f"a concrete IPv4 address is required: {value!r}")
    return str(address)


def configured_hosts_text(source: str, server_ip: str) -> str:
    server_ip = ipv4(server_ip)
    pattern = re.compile(
        rf"^\s*(?:\d{{1,3}}\.){{3}}\d{{1,3}}\s+{re.escape(CHAT_HOSTNAME)}(?:\s|$)",
        re.IGNORECASE,
    )
    lines = [line for line in source.splitlines() if not pattern.match(line)]
    lines.append(f"{server_ip} {CHAT_HOSTNAME} # ThorGor HoN LAN chat")
    return "\r\n".join(lines) + "\r\n"


def configure_chat_host(server_ip: str, hosts_path: Path | None = None) -> Path:
    if hosts_path is None:
        hosts_path = (
            Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "System32"
            / "drivers"
            / "etc"
            / "hosts"
        )
    source = hosts_path.read_text(encoding="ascii", errors="replace")
    hosts_path.write_text(configured_hosts_text(source, server_ip), encoding="ascii", newline="")
    subprocess.run(
        ["ipconfig.exe", "/flushdns"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    return hosts_path


def player_command(hon_home: Path, server_ip: str) -> list[str]:
    hon = hon_home / "hon.exe"
    if not hon.is_file():
        raise FileNotFoundError(f"hon.exe not found: {hon}")
    return [str(hon), "-masterserver", ipv4(server_ip)]


def chat_reachable(server_ip: str, timeout: float = 4.0) -> bool:
    try:
        with socket.create_connection((ipv4(server_ip), 11031), timeout=timeout):
            return True
    except OSError:
        return False


def setup(hon_home: Path, server_ip: str) -> None:
    for message in install_supported_patches(hon_home):
        print(message)
    configured = configure_chat_host(server_ip)
    print(f"Configured {CHAT_HOSTNAME} in {configured}")


def launch(hon_home: Path, server_ip: str) -> int:
    server_ip = ipv4(server_ip)
    if not chat_reachable(server_ip):
        raise ConnectionError(f"ThorGor chat is unreachable at {server_ip}:11031")
    command = player_command(hon_home, server_ip)
    subprocess.Popen(command, cwd=hon_home)
    print(f"Started HoN against ThorGor at {server_ip}")
    return 0


def setup_main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Install patches and configure a ThorGor remote client")
    parser.add_argument("--hon-home", type=Path, required=True)
    parser.add_argument("--server-ip", required=True)
    args = parser.parse_args(argv)
    try:
        setup(args.hon_home.expanduser().resolve(), ipv4(args.server_ip))
        SETUP_LOG.unlink(missing_ok=True)
        return 0
    except Exception:
        SETUP_LOG.parent.mkdir(parents=True, exist_ok=True)
        SETUP_LOG.write_text(traceback.format_exc(), encoding="utf-8")
        print(f"Remote-client setup failed. Details: {SETUP_LOG}")
        return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Launch a configured ThorGor remote LAN client")
    parser.add_argument("--hon-home", type=Path, required=True)
    parser.add_argument("--server-ip", required=True)
    args = parser.parse_args(argv)
    return launch(args.hon_home.expanduser().resolve(), args.server_ip)
