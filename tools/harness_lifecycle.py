"""Native console match termination and authoritative lifecycle observation."""
from __future__ import annotations

import time

from thorgor.game_manager.native_match_id import RemoteProcess, module_info
from thorgor.tools.harness_gameplay import inspect_gameplay, wait_state


def end_match(pid, clients, job, check, event):
    before = inspect_gameplay(pid)
    if before["phase"] != 6:
        raise RuntimeError("match termination needs an active native match")
    # C6 ReadRemoteCommandPacket requires native ADMIN flags. The creator
    # has them; the command and single winning-team argument are verified at
    # game.dll 6603D -> 21BC0 -> 21B60 (registered EndMatch server command).
    clients[0].reliable(b"\xc6EndMatch 1\0")
    event("native_end_match_requested", pid=pid, match_id=before["native_match_id"])
    ended = check("native_match_ended", lambda: wait_state(
        pid, clients, lambda state: state["phase"] == 7,
        "native_ended_phase", event, timeout=10))
    event("native_ended_state", state=ended)
    duration = ended["phase_duration"]
    timeout = min(180, duration / 1000 + 15) if duration != 0xFFFFFFFF else 60
    deadline = time.monotonic() + max(15, timeout)
    signature = None
    while time.monotonic() < deadline:
        for client in clients:
            client.poll()
        owned = job.pids()
        if job.pid not in owned:
            raise RuntimeError("native manager exited during match termination")
        if pid not in owned:
            import _winapi
            code = _winapi.GetExitCodeProcess(job.handles[pid])
            event("native_end_lifecycle", pid=pid, outcome="slave_exited", returncode=code,
                  owned_pids=sorted(owned))
            if code != 0:
                raise RuntimeError("native slave crashed after match termination")
            return {"outcome": "slave_exited", "pid": pid, "returncode": code}
        module = module_info(pid, "game.dll")
        if module is None:
            event("native_end_lifecycle", pid=pid, outcome="game_module_unloaded")
            return {"outcome": "game_module_unloaded", "pid": pid}
        with RemoteProcess(pid) as process:
            game = process.read_u32(module[0] + 0x9163C)
            info = process.read_u32(game + 0x78) if game else 0
        if not info:
            event("native_end_lifecycle", pid=pid, outcome="game_context_cleared")
            return {"outcome": "game_context_cleared", "pid": pid}
        state = inspect_gameplay(pid)
        current = (state["phase"], state["native_match_id"], len(state["players"]))
        if current != signature:
            event("native_end_lifecycle", pid=pid, outcome="observing", state=state)
            signature = current
        if state["phase"] in (0, 1) and not state["players"]:
            event("native_end_lifecycle", pid=pid, outcome="idle_empty", state=state)
            return {"outcome": "idle_empty", "pid": pid}
        time.sleep(0.05)
    event("native_end_lifecycle_timeout", state=state, timeout_seconds=timeout)
    raise TimeoutError("native match ended but slave did not return to idle")
