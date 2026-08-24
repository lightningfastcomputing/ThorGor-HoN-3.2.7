"""HoN 3.2.7.1 SRP and password compatibility primitives."""
from .server import (
    CHAT_SERVER_AUTHENTICATION_SALT,
    G,
    H,
    MAGIC1,
    MAGIC2,
    N,
    S2_N_HEX,
    WIDTH,
    encoded_num,
    hon_password,
    xor_bytes,
)

__all__ = ["S2_N_HEX", "N", "G", "WIDTH", "H", "xor_bytes", "encoded_num", "hon_password"]
