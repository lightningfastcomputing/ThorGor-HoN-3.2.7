"""Isolated Windows manager and dedicated-slave harness."""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid

from thorgor.game_manager.manager_process import manager_command


HOST = "127.0.0.1"
SLAVE_PORT = 11235
PROXY_PORT = 11236
MANAGER_PORT = 1136
BRIDGE_PORT = 1135
MASTER_URL = f"http://{HOST}/server_requester.php"
V39_HASHES = {
    "k2.dll": "CB12258566BA001B528F3A48E4C8CC795992DCB17333BCE5ABF8EF4E5DCCB24D",
    "game/game.dll": "0DA7FA068C813328BCF89CADAAB0EB9C17B5963B9C27E49298D6D6DEFCC9D43B",
}


def preflight():
    if os.name != "nt":
        raise RuntimeError("native-match requires Windows")
    from thorgor.tools.harness_job import running_hon
    if running_hon():
        raise RuntimeError("close existing HoN instances before native-match")
    for kind, ports in (
        (socket.SOCK_STREAM, (80, 11031, BRIDGE_PORT, MANAGER_PORT)),
        (socket.SOCK_DGRAM, (SLAVE_PORT, PROXY_PORT)),
    ):
        for port in ports:
            with socket.socket(socket.AF_INET, kind) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                probe.bind((HOST, port))


def stage_install(source, directory, event):
    from thorgor.patches.installer import file_hash, install_game_capacity, install_k2

    source = source.resolve(strict=True)
    install = directory / "Heroes of Newerth"
    install.mkdir()
    for entry in source.iterdir():
        if entry.is_file() and entry.suffix.lower() in {".dll", ".exe", ".crt"}:
            shutil.copyfile(entry, install / entry.name)
    for name in ("base", "game", "locales"):
        shutil.copytree(source / name, install / name, ignore=shutil.ignore_patterns(
            "*.thorgor_*", "*.dmp", "*.log", "login.cfg", "startup.cfg", "reconnect.cfg",
        ))
    if not (install / "hon.exe").is_file():
        raise FileNotFoundError("HoN installation has no hon.exe")
    for backup in ("k2.dll.thorgor_stock_3.2.7.1", "k2.dll.thorgor_linked_delivery_baseline",
                   "game/game.dll.thorgor_stock_3.2.7.1"):
        if (source / backup).is_file():
            shutil.copyfile(source / backup, install / backup)
    install_k2(install)
    install_game_capacity(install)
    hashes = {name: file_hash(install / name) for name in V39_HASHES}
    if hashes != V39_HASHES:
        raise ValueError("staged native DLLs do not match frozen v39")
    event("native_binary_hashes", sha256={"hon.exe": file_hash(install / "hon.exe"), **hashes})
    mod = "thorgor_harness_" + uuid.uuid4().hex
    shutil.copytree(install / "game", install / mod)
    return install, mod


def isolated_profile(stack, directory, mod, event):
    import ctypes
    documents = ctypes.create_unicode_buffer(260)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, documents)
    if result != 0:
        raise OSError("cannot locate the native HoN profile root")
    root = Path(documents.value) / "Heroes of Newerth"
    profile = root / mod
    profile.mkdir(parents=True, exist_ok=False)

    def remove():
        if profile.resolve().parent != root.resolve() or not profile.name.startswith("thorgor_harness_"):
            raise RuntimeError("test profile escaped its expected root")
        # This directory was created exclusively for this run.
        shutil.rmtree(profile)
        event("native_profile_removed")

    stack.callback(remove)
    shared_log = root / "game" / "console.log"
    saved_log = directory / "prior-console.log"
    if shared_log.exists():
        shutil.copy2(shared_log, saved_log)

    def restore_log():
        if saved_log.exists():
            shutil.copy2(saved_log, shared_log)
        else:
            shared_log.unlink(missing_ok=True)
        event("shared_console_log_restored")

    stack.callback(restore_log)
    event("native_profile_created", profile_name=mod)
    return profile


def bridge_frames(directory):
    path = directory / "work" / "manager_status_bridge_v42_events.jsonl"
    if not path.exists():
        return []
    # The last line may still be in flight.
    return [json.loads(line) for line in path.read_bytes().splitlines(keepends=True)
            if line.endswith(b"\n")]


def udp_owners(port, event=None):
    result = subprocess.run(["netstat.exe", "-ano", "-p", "udp"], capture_output=True,
                            text=True, timeout=5, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    listeners = {int(row[-1]): row[1] for line in result.stdout.splitlines()
                 if (row := line.split()) and len(row) == 4
                 and row[0] == "UDP" and row[1].endswith(f":{port}")}
    if event is not None:
        event("native_udp_bindings", listeners=listeners)
    return set(listeners)


def await_slave(job, directory):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        pids = job.pids()
        if job.pid not in pids:
            raise RuntimeError("native manager exited during startup")
        frames = bridge_frames(directory)
        associated = {frame["connection"] for frame in frames
                      if frame["kind"] == "real_slave_association"}
        ready = any(frame.get("connection") in associated and (
            frame["kind"] == "genuine_manager_wake" or
            frame["kind"] == "real_slave_status" and frame["status"] in (0, 1)
        ) for frame in frames)
        if ready:
            owners = udp_owners(SLAVE_PORT) & (pids - {job.pid})
            if len(owners) == 1:
                slave = owners.pop()
                job.track(slave)
                return slave
        time.sleep(0.25)
    raise TimeoutError("no owned dedicated slave reached manager readiness")


def inspect_launch(job, event, pid=None):
    import ctypes
    from thorgor.game_manager.native_match_id import module_info, RemoteProcess, kernel32
    pid = job.pid if pid is None else pid
    mod = module_info(pid, "k2.dll")
    if mod is None:
        event("native_launch_inspection", k2_loaded=False)
        return
    with RemoteProcess(pid) as proc:
        system = proc.read_u32(mod[0] + 0x90D734)

        def string(offset):
            address = system + offset
            length = proc.read_u32(address + 0x14)
            capacity = proc.read_u32(address + 0x18)
            if length > 4096:
                raise ValueError("unexpected native string length")
            if capacity >= 8:
                address = proc.read_u32(address + 4)
            else:
                address += 4
            data = ctypes.create_string_buffer(length * 2)
            read = ctypes.c_size_t()
            if not kernel32.ReadProcessMemory(proc.handle, ctypes.c_void_p(address),
                                             data, len(data), ctypes.byref(read)):
                raise ctypes.WinError()
            return data.raw.decode("utf-16le")

        command = string(0x104)
        registration = re.search(r"-register\s+([0-9.:]+)", command)
        event("native_launch_inspection", pid=pid, k2_loaded=True,
              manager_switch="-manager" in command, noconfig_switch="-noconfig" in command,
              command_characters=len(command), command_prefix=command[:35],
              register_endpoint=registration[1] if registration else None,
              manager_mode=proc.read_u8(system + 0x3AB),
              dedicated_mode=proc.read_u8(system + 0x3A9))


def inspect_job(job, event):
    for pid in job.pids():
        try:
            inspect_launch(job, event, pid)
        except (OSError, ValueError) as error:
            event("native_inspection_unavailable", pid=pid, error=type(error).__name__)


def record_bridge(directory, event):
    frames = bridge_frames(directory)
    counts = Counter(f"{frame['direction']}:{frame['opcode']}" for frame in frames
                     if frame["kind"] == "control_frame")
    statuses = [frame["status"] for frame in frames if frame["kind"] == "real_slave_status"]
    event("native_control_summary", frame_counts=dict(counts), slave_statuses=statuses,
          manager_wakes=sum(frame["kind"] == "genuine_manager_wake" for frame in frames),
          associations=sum(frame["kind"] == "real_slave_association" for frame in frames))
    event("native_control_log", frames=[
        {key: value for key, value in frame.items()
         if key in ("timestamp", "kind", "direction", "opcode", "payload_length", "status")}
        for frame in frames if frame["kind"] == "control_frame"
    ][-200:])
    event("native_bridge_actions", actions=[
        {key: value for key, value in frame.items()
         if key in ("timestamp", "kind", "match_id", "opcode")}
        for frame in frames if frame["kind"] == "native_start_game"
    ])
    state_path = directory / "work/v31_registration_state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
        event("native_state_snapshot", state={
            key: state[key] for key in (
                "manager_association_real", "manager_associated", "manager_control_connected",
                "manager_status_source", "server_status", "lifecycle", "match_id",
                "native_start_game_injected", "slave_start_game_result_seen",
            ) if key in state
        })


def record_proxy(directory, event):
    path = directory / "work/hon_udp_shim_public_list.log"
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    samples = re.findall(r"ROUTE_STATS .*to_server=(\d+)pkt/\d+B from_server=(\d+)pkt", text)
    event("native_proxy_summary", sampled_to_server_packets=sum(int(a) for a, _ in samples),
          sampled_from_server_packets=sum(int(b) for _, b in samples),
          samples=len(samples), accepted_c0=text.count("C0_AUTH_ACCEPT "),
          rejected_c0=text.count("C0_AUTH_REJECT "),
          native_assignments=text.count("NATIVE_CLIENT_ASSIGNED "))


def record_native_logs(install, event):
    for path in install.rglob("native_manager.log"):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        errors = [line[:300] for line in lines if any(word in line.lower()
                  for word in ("error", "failed", "exception", "unknown command"))
                  and not any(word in line.lower() for word in ("password", "cookie", "session"))]
        event("native_console_summary", log=path.relative_to(install).as_posix(),
              line_count=len(lines), diagnostic_lines=errors[-12:])


def run_native(stack, directory, env, staged, master, chat, passwords, check, event, *,
               admit_clients=False):
    from thorgor.tools.harness import authenticate, start_process, wait_listener
    from thorgor.tools.harness_job import NativeJob
    install, mod = staged
    check("isolate_native_profile", lambda: isolated_profile(stack, directory, mod, event))

    def start_bridge():
        process, log = start_process(
            stack, directory, env, "manager_bridge",
            [sys.executable, "-u", "-m", "thorgor", "game-manager", "--listen-host", HOST,
             "--listen-port", str(BRIDGE_PORT), "--target-port", str(MANAGER_PORT),
             "--master-url", MASTER_URL], event,
        )
        wait_listener(process, log, f"Listening: TCP {HOST}:")

    def start_proxy():
        process, log = start_process(
            stack, directory, env, "udp_proxy",
            [sys.executable, "-u", "-m", "thorgor", "udp-shim",
             "--preset", "thorgor-public-list", "--listen-host", HOST,
             "--browser-ip", HOST, "--require-c0-auth", "--master-url", MASTER_URL,
             "--manager-start-timeout", "3", "--stats-interval", "1"], event,
        )
        wait_listener(process, log, f"Listening: UDP {HOST}:")

    check("start_manager_bridge", start_bridge)
    check("start_udp_proxy", start_proxy)
    command = manager_command(install, settings=(
        f"Set man_masterPassword {passwords['thorgorhost:1']}",
        f"Set net_forceIP {HOST}", "Set con_logFile :/native_manager.log", "Set con_writeLog true",
        "Set sv_autosaveReplay false", "Set sys_autoSaveDump false", "Set sys_dumpOnFatal false",
    ))
    command[1:1] = ["-dedicated", "-mod", mod]
    job = check("launch_manager", lambda: NativeJob(command, install, env))
    stack.callback(lambda: event("native_processes_stopped", returncodes=job.stop()))
    stack.callback(record_bridge, directory, event)
    stack.callback(record_proxy, directory, event)
    stack.callback(record_native_logs, install, event)
    stack.callback(inspect_job, job, event)
    event("native_manager_started", pid=job.pid)
    time.sleep(2)
    check("inspect_native_launch", lambda: inspect_launch(job, event))
    slave = check("native_slave_ready", lambda: await_slave(job, directory))
    event("native_slave_listening", pid=slave, udp_port=SLAVE_PORT)
    udp_owners(SLAVE_PORT, event)
    def verify_loaded_game():
        from thorgor.game_manager.native_match_id import module_info
        from thorgor.patches.installer import file_hash
        loaded = module_info(slave, "game.dll")
        if loaded is None or not loaded[1].resolve().is_relative_to(install.resolve()):
            raise ValueError("owned native slave did not load the staged game DLL")
        actual = file_hash(loaded[1])
        if actual != V39_HASHES["game/game.dll"]:
            raise ValueError("loaded native slave has an unexpected game DLL hash")
        event("native_loaded_game", sha256=actual)

    check("verify_loaded_game", verify_loaded_game)
    creator, joiner = authenticate(master, chat, passwords, check)
    if admit_clients:
        from thorgor.tools.harness_clients import NativeClient
        from thorgor.tools.harness_clients import post
        from thorgor.protocols.php_wire import parse_php_string_field
        picker = post(master, f="server_list", cookie=creator.cookie, gametype="90")
        key = parse_php_string_field(picker, "acc_key")
        clients = []
        for username, identity, host_key in (("creator", creator, key), ("joiner", joiner, "")):
            client = NativeClient(username, identity, host_key)
            clients.append(client)
            stack.callback(client.close)
            stack.callback(lambda client=client, username=username: event(
                "native_client_summary", username=username, sent=client.sent,
                received=client.received, native_number=client.native_number,
                packet_types=client.packet_types, bootstrapped=client.bootstrapped,
            ))
        check("bootstrap_creator", clients[0].admit)

        def create_lobby():
            wire = post(master, "/server_requester.php", f="host_lobby",
                        cookie=creator.cookie, host_key=key, version="3.2.7.1",
                        mname="ThorGor unattended", map="caldavar",
                        options="map:caldavar teamsize:5 mode:botmatch allowduplicate:true")
            match = re.search(rb's:8:"match_id";i:([1-9][0-9]*);', wire)
            if match is None:
                raise ValueError("backend did not allocate the native lobby")
            return int(match[1])

        match_id = check("create_native_lobby", create_lobby)
        check("native_lobby_context", lambda: await_lobby(
            slave, match_id, clients[:1], directory, event,
        ))
        check("bootstrap_joiner", clients[1].admit)
        check("independent_native_clients", lambda: await_players(
            slave, match_id, clients, {creator.account_id, joiner.account_id}, event,
        ))
    if {job.pid, slave} - job.pids():
        raise RuntimeError("native process exited during the smoke test")



def await_lobby(slave, match_id, clients, directory, event):
    from thorgor.game_manager.native_match_id import synchronize_pid
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        for client in clients:
            client.poll()
        frames = bridge_frames(directory)
        results = [frame for frame in frames
                   if frame["kind"] == "real_slave_start_game_result"]
        if not any(frame["kind"] == "native_start_game" and frame.get("match_id") == match_id
                   for frame in frames):
            continue
        try:
            action, info = synchronize_pid(slave, match_id)
        except (OSError, RuntimeError):
            continue
        if action in ("already_synced", "written"):
            event("native_match_context", match_id=match_id, synchronization=action,
                  start_result_status=results[-1]["decoded"]["status"] if results else None)
            return info
        raise RuntimeError("native match-ID synchronization refused")
    raise TimeoutError("native lobby context did not become ready")


def await_players(slave, match_id, clients, accounts, event):
    from thorgor.game_manager.native_match_id import inspect_native_match_id, inspect_native_players
    deadline = time.monotonic() + 20
    players = []
    while time.monotonic() < deadline:
        for client in clients:
            client.poll()
        info = inspect_native_match_id(slave)
        if info["native_match_id"] != match_id:
            raise RuntimeError("native lobby match ID changed")
        players = inspect_native_players(slave, info["cgame"])
        selected = [player for player in players if player["account_id_low30"] in accounts]
        if (len(selected) == 2 and {p["account_id_low30"] for p in selected} == accounts
                and len({p["native_client_number"] for p in selected}) == 2
                and all(p["connection_status"] & 0x40 for p in selected)):
            event("native_players", players=selected)
            return
    event("native_players", players=players)
    raise TimeoutError("two independent connected players did not appear in the native roster")
