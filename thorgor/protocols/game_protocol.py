"""Public UDP game protocol and compatibility shim."""
from thorgor.compat import load_legacy

_legacy = load_legacy("udp_shim", "hon_udp_shim.py")
ConnectC0 = _legacy.ConnectC0
build_proxy_challenge = _legacy.build_proxy_challenge
parse_lobby_create = _legacy.parse_lobby_create
parse_connect_c0 = _legacy.parse_connect_c0
validate_c_conn_response = _legacy.validate_c_conn_response


def main(argv=None) -> int:
    return int(_legacy.main() or 0)

