"""Run named end-to-end backend scenarios in a disposable local environment."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from thorgor.tools.harness_clients import chat_auth, expect_chat_acceptance, login, post
from thorgor.protocols.admission import validate_c_conn_response


ROOT = Path(__file__).resolve().parents[1]
LOOPBACK = "127.0.0.1"


def authenticate(master, chat, passwords, check):
    check("incorrect_password", lambda: login(master, "creator", passwords["joiner"], reject=True))
    creator = check("creator_srp", lambda: login(master, "creator", passwords["creator"]))
    joiner = check("joiner_srp", lambda: login(master, "joiner", passwords["joiner"]))
    check("distinct_accounts", lambda: require(
        creator.account_id != joiner.account_id and creator.cookie != joiner.cookie,
        "master reused the account ID or cookie",
    ))
    def reject_foreign_cookie():
        with socket.create_connection((LOOPBACK, chat), timeout=3) as connection:
            chat_auth(connection, creator, joiner.cookie)
            connection.shutdown(socket.SHUT_WR)
            require(connection.recv(1) == b"", "chat responded to a cross-account cookie")

    check("cross_account_chat_cookie", reject_foreign_cookie)
    with socket.create_connection((LOOPBACK, chat), timeout=3) as first:
        check("creator_chat", lambda: connect_chat(first, creator))
        with socket.create_connection((LOOPBACK, chat), timeout=3) as second:
            check("joiner_chat", lambda: connect_chat(second, joiner))
    return creator, joiner


def connect_chat(connection, identity):
    chat_auth(connection, identity, identity.cookie)
    expect_chat_acceptance(connection)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def lobby_authority(master, chat, passwords, check):
    creator, joiner = authenticate(master, chat, passwords, check)
    key = secrets.token_hex(16)
    path = "/server_requester.php"

    def admission(identity, expected_host, host_key=""):
        wire = post(master, path, f="c_conn", cookie=identity.cookie, host_key=host_key)
        accepted, _, host, account = validate_c_conn_response(wire, identity.cookie)
        require(accepted and host == expected_host and account == identity.account_id,
                "admission returned unexpected authority or account identity")

    def release(identity):
        wire = post(master, path, f="host_release", cookie=identity.cookie, host_key=key)
        require(b's:7:"success";i:1;' in wire, "unexpected reservation release response")

    check("creator_reserves", lambda: admission(creator, True, key))
    check("ordinary_joiner", lambda: admission(joiner, False))
    check("joiner_cannot_claim_creator_key", lambda: admission(joiner, False, key))
    check("joiner_release_request", lambda: release(joiner))
    check("joiner_cannot_take_released_key", lambda: admission(joiner, False, key))
    check("creator_retains_reservation", lambda: admission(creator, True, key))
    check("creator_release_request", lambda: release(creator))
    check("next_creator_can_reserve", lambda: admission(joiner, True, key))


SCENARIOS = {"auth": authenticate, "lobby-authority": lobby_authority}


def start_service(stack, directory, env, service, db_args, event):
    log_path = directory / f"{service}.stdout"
    command = [sys.executable, "-u", "-m", "thorgor", service,
               "--host", LOOPBACK, "--port", "0", *db_args]
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT)

    def stop():
        early_exit = process.poll()
        if early_exit is None:
            process.kill()
        process.wait(timeout=5)
        event(f"{service}_stopped", pid=process.pid, returncode=process.returncode)
        if early_exit is not None:
            raise RuntimeError(f"{service} exited unexpectedly with code {early_exit}")

    stack.callback(stop)
    event(f"{service}_started", pid=process.pid)
    prefix = f"Listening: {'http://' if service == 'master' else 'TCP '}{LOOPBACK}:"
    pattern = re.compile(re.escape(prefix) + r"([1-9][0-9]*)\r?\n")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and process.poll() is None:
        match = pattern.search(log_path.read_text(encoding="utf-8", errors="replace"))
        if match:
            return int(match[1])
        time.sleep(0.05)
    raise RuntimeError(f"{service} did not publish its bound loopback port")


def run(scenario):
    events = []
    report = {"scenario": scenario, "scope": "simulated backend protocol",
              "status": "failed", "events": events}

    def event(name, **fields):
        events.append({"time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                       "name": name, **fields})

    def check(name, operation):
        event(name, status="running")
        try:
            result = operation()
        except Exception as error:
            # Existing wire diagnostics can include credentials. Export only safe metadata.
            event(name, status="failed", error=type(error).__name__)
            raise
        event(name, status="passed")
        return result

    def exercise(temp, stack):
        directory = Path(temp)
        env = {**os.environ, "THORGOR_DATA_HOME": str(directory)}
        database = directory / "accounts.db"
        passwords = {name: secrets.token_urlsafe(24) for name in ("creator", "joiner")}

        def provision():
            for username, password in passwords.items():
                subprocess.run(
                    [sys.executable, "-m", "thorgor", "master", "--database", str(database),
                     "--add-account-env", username, "THORGOR_HARNESS_PASSWORD"],
                    cwd=ROOT, env={**env, "THORGOR_HARNESS_PASSWORD": password},
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=10, check=True,
                )

        check("provision_accounts", provision)
        master = check("start_master", lambda: start_service(
            stack, directory, env, "master", ["--database", str(database)], event))
        chat = check("start_chat", lambda: start_service(
            stack, directory, env, "chat", ["--db", str(database)], event))
        SCENARIOS[scenario](master, chat, passwords, check)

    try:
        with TemporaryDirectory(prefix="thorgor-harness-") as temp:
            try:
                with ExitStack() as stack:
                    exercise(temp, stack)
            except Exception as error:
                event("run_failed", error=type(error).__name__)
            else:
                report["status"] = "passed"
        event("runtime_removed")
    except Exception as error:
        report["status"] = "failed"
        event("runtime_error", error=type(error).__name__)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--report", type=Path, help="also write the JSON result to this new file")
    args = parser.parse_args(argv)
    report = run(args.scenario)
    output = json.dumps(report, indent=2) + "\n"
    print(output, end="")
    if args.report:
        with args.report.open("x", encoding="utf-8") as handle:
            handle.write(output)
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
