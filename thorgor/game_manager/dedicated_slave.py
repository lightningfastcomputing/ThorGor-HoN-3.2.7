"""Adapter for the verified manager/slave control bridge."""
from thorgor.compat import load_legacy

_legacy = load_legacy("manager_bridge_v42", "hon_manager_status_bridge_v42.py")
BridgeState = _legacy.BridgeState
FrameDecoder = _legacy.FrameDecoder


def main(argv=None) -> int:
    return int(_legacy.main() or 0)

