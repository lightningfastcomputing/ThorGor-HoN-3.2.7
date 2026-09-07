from __future__ import annotations

import ctypes
import os
import socket
from ctypes import wintypes


DEDICATED_CPU_ENV = "THORGOR_DEDICATED_CPU"


def resolve_dedicated_cpu(value: str | None = None, logical_cpus: int | None = None) -> int | None:
    """Resolve the logical CPU reserved for the dedicated slave."""
    count = logical_cpus if logical_cpus is not None else min(os.cpu_count() or 1, ctypes.sizeof(ctypes.c_size_t) * 8)
    raw = (value if value is not None else os.environ.get(DEDICATED_CPU_ENV, "auto")).strip().lower()
    if raw in {"off", "none", "all", "-1"}:
        return None
    if raw in {"", "auto"}:
        return count - 1 if count >= 4 else None
    try:
        cpu = int(raw, 10)
    except ValueError as exc:
        raise ValueError(f"{DEDICATED_CPU_ENV} must be 'auto', 'off', or a logical CPU number") from exc
    if not 0 <= cpu < count:
        raise ValueError(f"logical CPU {cpu} is outside this machine's 0..{count - 1} range")
    return cpu


def client_affinity_mask(reserved_cpu: int | None, logical_cpus: int | None = None) -> int | None:
    """Return a mask that leaves the server CPU and its adjacent sibling unused."""
    if reserved_cpu is None:
        return None
    count = logical_cpus if logical_cpus is not None else min(os.cpu_count() or 1, ctypes.sizeof(ctypes.c_size_t) * 8)
    if not 0 <= reserved_cpu < count:
        raise ValueError("reserved CPU is outside the available logical CPU range")
    reserved_mask = 1 << reserved_cpu
    # Windows normally numbers SMT siblings adjacently. Keeping that companion
    # idle prevents a rendering thread on the sibling from stealing execution
    # resources from the dedicated simulation's physical core. On hybrid CPUs
    # this may reserve a second small core, which is still preferable to jitter.
    sibling = reserved_cpu ^ 1
    if count >= 4 and sibling < count:
        reserved_mask |= 1 << sibling
    mask = ((1 << count) - 1) & ~reserved_mask
    return mask or None


def server_is_local(server_ip: str) -> bool:
    """Return whether the server address is hosted by this machine."""
    if server_ip.startswith("127."):
        return True
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((server_ip, 11031))
        return sock.getsockname()[0] == server_ip
    except OSError:
        return False
    finally:
        sock.close()


def set_process_affinity(pid: int, mask: int | None) -> None:
    """Apply a Windows process-affinity mask to a newly launched local client."""
    if mask is None or os.name != "nt":
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    kernel32.SetProcessAffinityMask.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    process = kernel32.OpenProcess(0x0200 | 0x0400, False, pid)
    if not process:
        raise OSError(ctypes.get_last_error(), f"could not open process {pid} for affinity")
    try:
        if not kernel32.SetProcessAffinityMask(process, ctypes.c_size_t(mask)):
            raise OSError(ctypes.get_last_error(), f"could not set affinity for process {pid}")
    finally:
        kernel32.CloseHandle(process)
