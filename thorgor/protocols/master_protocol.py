"""Master-server serialization primitives."""
from thorgor.compat import load_legacy

_legacy = load_legacy("master_v39", "thorgor_hon_sandboxed_masterserver_v39.py")
php_serialize = _legacy.php_serialize
match_server_list_payload = _legacy.match_server_list_payload
error_payload = _legacy.error_payload

__all__ = ["php_serialize", "match_server_list_payload", "error_payload"]

