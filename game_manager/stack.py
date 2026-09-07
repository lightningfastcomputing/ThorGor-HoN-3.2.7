"""Typed description of the ThorGor service stack.

The dashboard renders and starts this plan; it does not own service-specific
arguments or startup ordering.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ServiceSpec:
    name: str
    module: str
    arguments: tuple[str, ...] = ()
    working_directory: Path | None = None
    start_after_ms: int = 0


def build_stack(
    *,
    lan_ip: str,
    hon_home: Path,
    package_parent: Path,
    data_root: Path,
) -> tuple[ServiceSpec, ...]:
    """Return the canonical, behavior-compatible ThorGor startup plan."""
    master_url = "http://127.0.0.1/server_requester.php"
    return (
        ServiceSpec(
            "master",
            "thorgor.master.server",
            (
                "--host", "0.0.0.0", "--port", "80", "--password-chain", "pre-md5",
                "--chat-host", lan_ip, "--server-list-ip", lan_ip,
                "--server-list-port", "11236", "--match-server-ip", "127.0.0.1",
                "--match-server-port", "11235", "--match-server-location", "USE",
            ),
            package_parent,
        ),
        ServiceSpec(
            "chat",
            "thorgor.chat.server",
            (
                "--host", "0.0.0.0", "--port", "11031",
                "--db", str(data_root / "thorgor_accounts.db"),
                "--match-host", lan_ip, "--match-port", "11236",
            ),
            package_parent,
            2000,
        ),
        ServiceSpec(
            "udp",
            "thorgor.protocols.game_protocol",
            (
                "--preset", "thorgor-public-list", "--listen-host", "0.0.0.0",
                "--listen-port", "11236", "--browser-ip", lan_ip, "--require-c0-auth",
                "--master-url", master_url, "--manager-start-timeout", "3",
                "--max-client-routes", "16", "--client-route-timeout", "600",
                "--stats-interval", "1",
            ),
            package_parent,
            2000,
        ),
        ServiceSpec(
            "backend",
            "thorgor.game_manager.dedicated_slave",
            (
                "--listen-host", "127.0.0.1", "--listen-port", "1135",
                "--target-port", "1136", "--master-url", master_url,
            ),
            package_parent,
            1000,
        ),
        ServiceSpec(
            "manager",
            "thorgor.game_manager.manager_process",
            ("--hon-home", str(hon_home)),
            package_parent,
            1000,
        ),
        ServiceSpec(
            "native",
            "thorgor.game_manager.native_match_id",
            (),
            package_parent,
            15000,
        ),
    )
