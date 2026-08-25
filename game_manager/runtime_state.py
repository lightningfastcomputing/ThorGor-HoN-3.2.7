from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path

from thorgor.paths import ROOT


WORK_FILES = (
    "manager_status_bridge_v42.log",
    "manager_status_bridge_v42_events.jsonl",
    "v42_manager_control.connected",
    "manager_status_bridge_v39.log",
    "v39_manager_control.connected",
    "hon_udp_shim_public_list.log",
    "v31_registration_state.json",
    "v31_registration_state.tmp",
    "v31_registration_state.bridge.tmp",
    "v31_registration_state.chat.tmp",
    "v42_run_id.txt",
)
WORK_DIRECTORIES = (
    "manager_status_bridge_v42_captures",
    "manager_status_bridge_v39_captures",
)


def reset_runtime_state(root: Path = ROOT) -> str:
    root = root.resolve()
    work = root / "work"
    chat = root / "chat-server"
    work.mkdir(parents=True, exist_ok=True)
    for name in WORK_FILES:
        (work / name).unlink(missing_ok=True)
    for name in WORK_DIRECTORIES:
        shutil.rmtree(work / name, ignore_errors=True)
    for name in ("thorgor_srp_v39.log", "thorgor_server_v39.log"):
        (root / name).unlink(missing_ok=True)
    for name in ("thorgor_srp_v39_captures", "thorgor_server_v39_captures"):
        shutil.rmtree(root / name, ignore_errors=True)
    for name in ("thorgor_chat_v13.log", "thorgor_chat_v13_host.log"):
        (chat / name).unlink(missing_ok=True)
    for name in ("thorgor_chat_v13_captures", "thorgor_chat_v13_host_captures"):
        shutil.rmtree(chat / name, ignore_errors=True)
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}"
    (work / "v42_run_id.txt").write_text(run_id + "\n", encoding="utf-8")
    return run_id


def main(argv=None) -> int:
    print(f"ThorGor runtime state reset. Run ID: {reset_runtime_state()}")
    return 0
