"""HoN 3.2.7.1 password and SRP compatibility primitives."""
from __future__ import annotations

import hashlib

S2_N_HEX = (
    "DA950C6C97918CAE89E4F5ECB32461032A217D740064BC12FC0723CD204BD02A7AE29B53F3310C13BA998B7910F8B6A14112CBC67BDD2427E"
    "DF494CB8BCA68510C0AAEE5346BD320845981546873069B337C073B9A9369D500873D647D261CCED571826E54C6089E7D5085DC2AF01FD861"
    "AE44C8E64BCA3EA4DCE942C5F5B89E5496C2741A9E7E9F509C261D104D11DD4494577038B33016E28D118AE4FD2E85D9C3557A2346FAECED3"
    "EDBE0F4D694411686BA6E65FEE43A772DC84D394ADAE5A14AF33817351D29DE074740AA263187AB18E3A25665EACAA8267C16CDE064B1D5AF"
    "0588893C89C1556D6AEF644A3BA6BA3F7DEC2F3D6FDC30AE43FBD6D144BB"
)
N = int(S2_N_HEX, 16)
G = 2
WIDTH = 0x100
MAGIC1 = "[!~esTo0}"
MAGIC2 = "taquzaph_?98phab&junaj=z=kuChusu"
CHAT_SERVER_AUTHENTICATION_SALT = "8roespiemlasToUmiuglEhOaMiaSWlesplUcOAniupr2esPOeBRiudOEphiutOuJ"


def int_bytes(value: int) -> bytes:
    return b"\x00" if value == 0 else value.to_bytes((value.bit_length() + 7) // 8, "big")


def pad_num(value: int) -> bytes:
    return value.to_bytes(WIDTH, "big")


def H(*parts: bytes) -> bytes:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part)
    return digest.digest()


def xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def encoded_num(value: int, *, padded: bool) -> bytes:
    return pad_num(value) if padded else int_bytes(value)


def hon_password(password: str, salt2: str, chain: str) -> str:
    material = hashlib.md5(password.encode("utf-8")).hexdigest() if chain == "pre-md5" else password
    stage1 = hashlib.md5((material + salt2 + MAGIC1).encode("utf-8")).hexdigest()
    return hashlib.sha256((stage1 + MAGIC2).encode("utf-8")).hexdigest()


__all__ = ["S2_N_HEX", "N", "G", "WIDTH", "H", "xor_bytes", "encoded_num",
           "hon_password", "int_bytes", "pad_num", "MAGIC1", "MAGIC2",
           "CHAT_SERVER_AUTHENTICATION_SALT"]
