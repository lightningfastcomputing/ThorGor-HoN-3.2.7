"""HoN 3.2.7.1 SRP and password compatibility primitives."""
from thorgor.compat import load_legacy

_legacy = load_legacy("master_v39", "thorgor_hon_sandboxed_masterserver_v39.py")
S2_N_HEX = _legacy.S2_N_HEX
N = _legacy.N
G = _legacy.G
WIDTH = _legacy.WIDTH
MAGIC1 = _legacy.MAGIC1
MAGIC2 = _legacy.MAGIC2
CHAT_SERVER_AUTHENTICATION_SALT = _legacy.CHAT_SERVER_AUTHENTICATION_SALT
H = _legacy.H
xor_bytes = _legacy.xor_bytes
encoded_num = _legacy.encoded_num
hon_password = _legacy.hon_password

__all__ = ["S2_N_HEX", "N", "G", "WIDTH", "H", "xor_bytes", "encoded_num", "hon_password"]

