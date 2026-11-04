"""Read-only, hash-gated native registry and snapshot-generation evidence."""
from __future__ import annotations

import ipaddress

from thorgor.game_manager.native_match_id import RemoteProcess, module_info
from thorgor.patches.installer import file_hash
from thorgor.tools.harness_native import V39_HASHES


def read_endpoint(process, connection):
    # Audited GetClientConnection: MSVC wstring at +1AC, ushort port at +1E4.
    address = connection + 0x1AC
    length = process.read_u32(address + 0x14)
    if not 0 < length <= 64:
        raise ValueError("invalid native endpoint length")
    buffer = process.read_u32(address + 4) if process.read_u32(address + 0x18) >= 8 else address + 4
    raw = bytes(process.read_u8(buffer + offset) for offset in range(length * 2))
    host = str(ipaddress.ip_address(raw.decode("utf-16-le")))
    return [host, process.read_u32(connection + 0x1E4) & 0xFFFF]


def read_connection(process, pointer):
    return {"connection": f"0x{pointer:08X}",
            "native_client_number": process.read_u32(pointer + 8),
            "account_id_low30": process.read_u32(pointer + 12) & 0x3FFFFFFF,
            "flags": process.read_u32(pointer + 0xCC),
            "state": process.read_u32(pointer + 0x8228),
            "last_receive_time": process.read_u32(pointer + 0x822C),
            "last_acked_frame": process.read_u32(pointer + 0x8230),
            "next": f"0x{process.read_u32(pointer + 0x8430):08X}",
            "endpoint": read_endpoint(process, pointer)}


def read_transport(process, base):
    # g_pHost export -> CHost::GetServer. Patched GetClient and packet loops
    # enumerate CHostServer+180 followed by CClientConnection+8430.
    host = process.read_u32(base + 0x8D82CC)
    server = process.read_u32(host + 0x78)
    head = process.read_u32(server + 0x180)
    clients = []
    pointer = head
    seen = set()
    while pointer:
        if pointer in seen or len(seen) >= 64:
            raise ValueError("native connection registry cycle or excessive length")
        seen.add(pointer)
        clients.append(read_connection(process, pointer))
        pointer = process.read_u32(pointer + 0x8430)
    # CHostServer::Frame increments +108 and writes the current snapshot into
    # vector +128, position +134. CSnapshot::GetByHandle is pool + handle*84.
    begin = process.read_u32(server + 0x128)
    end = process.read_u32(server + 0x12C)
    index = process.read_u32(server + 0x134)
    snapshot = None
    if index != 0xFFFFFFFF and begin and 0 <= index < (end - begin) // 4 <= 4096:
        handle = process.read_u32(begin + index * 4)
        if handle != 0xFFFFFFFF:
            if handle >= 0x100000:
                raise ValueError("invalid native snapshot pool handle")
            pool = process.read_u32(base + 0x8DBFE8)
            entry = pool + handle * 0x84
            snapshot = {"handle": handle, "valid": process.read_u8(entry) != 0,
                        "frame": process.read_u32(entry + 4),
                        "engine_time": process.read_u32(entry + 12)}
    return {"server": f"0x{server:08X}", "registry_head": f"0x{head:08X}",
            "server_frame": process.read_u32(server + 0x108),
            "server_time": process.read_u32(server + 0x118),
            "generated_snapshot": snapshot, "clients": clients}


class TransportProbe:
    def __init__(self, pid, expected_hash=None):
        module = module_info(pid, "k2.dll")
        if module is None or file_hash(module[1]) != (expected_hash or V39_HASHES["k2.dll"]):
            raise ValueError("native transport probe requires the verified staged K2")
        self.pid, self.base = pid, module[0]

    def inspect(self):
        with RemoteProcess(self.pid) as process:
            return read_transport(process, self.base)
