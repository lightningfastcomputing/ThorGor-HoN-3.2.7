"""LAN chat service entry point."""
from thorgor.compat import load_legacy

_legacy = load_legacy("chat_v13", "chat-server/thorgor_hon_chatserver_v13.py")
ChatWorld = _legacy.ChatWorld
ChatConnection = _legacy.ChatConnection


def main(argv=None) -> int:
    return int(_legacy.main() or 0)

