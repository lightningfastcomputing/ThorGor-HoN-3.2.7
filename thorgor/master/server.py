"""Master/auth HTTP service entry point."""
from thorgor.compat import load_legacy

_legacy = load_legacy("master_v39", "thorgor_hon_sandboxed_masterserver_v39.py")
Config = _legacy.Config
Handler = _legacy.Handler
Server = _legacy.Server


def main(argv=None) -> int:
    # The frozen implementation owns argparse until its handler migration.
    return _legacy.main()

