"""Login and game-authorization session boundary."""
from thorgor.compat import load_legacy

_legacy = load_legacy("master_v39", "thorgor_hon_sandboxed_masterserver_v39.py")
Session = _legacy.Session
Runtime = _legacy.Runtime
create_session = _legacy.create_session
preauth_payload = _legacy.preauth_payload
success_payload = _legacy.success_payload

__all__ = ["Session", "Runtime", "create_session", "preauth_payload", "success_payload"]

