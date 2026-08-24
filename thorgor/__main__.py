from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="thorgor")
    sub = parser.add_subparsers(dest="command", required=True)
    for service in ("master", "chat", "game-manager", "udp-shim", "dashboard"):
        sub.add_parser(service, help=f"run the {service} service")
    patches = sub.add_parser("patches", help="inspect or apply named binary patches")
    patches.add_argument("action", choices=("list", "show", "apply"))
    patches.add_argument("patch_id", nargs="?")
    patches.add_argument("source", nargs="?")
    patches.add_argument("target", nargs="?")
    args, passthrough = parser.parse_known_args()

    if args.command == "patches":
        from thorgor.patches.cli import run
        return run(args)
    if args.command == "master":
        from thorgor.master.server import main as entry
    elif args.command == "chat":
        from thorgor.chat.server import main as entry
    elif args.command == "game-manager":
        from thorgor.game_manager.dedicated_slave import main as entry
    elif args.command == "udp-shim":
        from thorgor.protocols.game_protocol import main as entry
    else:
        from thorgor.tools.dashboard import main as entry
    original_argv = sys.argv
    try:
        sys.argv = [original_argv[0], *passthrough]
        return int(entry(passthrough) or 0)
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    raise SystemExit(main())
