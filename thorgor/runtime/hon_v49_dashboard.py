"""ThorGor HoN v49 LAN status dashboard.

UI-only launcher wrapper for 1_START_V49_LAN_DEDICATED.bat.
The service commands, arguments, working directories, ports, and startup order
mirror the original v49 LAN launcher. Consoles are hidden and output is sent to
per-service log files so the backend behavior remains unchanged.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import tkinter as tk
import zipfile
import shutil
import json
import ipaddress
import contextlib
import ctypes
import threading
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox

IS_FROZEN = bool(getattr(sys, "frozen", False))
ROOT = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent
HON_HOME = Path(os.environ.get("THORGOR_HON_HOME", r"C:\Program Files (x86)\Heroes of Newerth"))
HON_EXE = HON_HOME / "hon.exe"
LOG_DIR = ROOT / "dashboard_logs"
LOG_DIR.mkdir(exist_ok=True)

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
FLAGS = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

def _valid_ipv4(value: str) -> str | None:
    value = (value or "").strip()
    try:
        ip = ipaddress.ip_address(value)
        if ip.version == 4 and not ip.is_unspecified:
            return str(ip)
    except ValueError:
        pass
    return None

def _autodetect_lan_ipv4() -> str:
    # Prefer the IPv4 selected by Windows for the default route. UDP connect
    # does not need a successful Internet exchange; it asks the OS which local
    # interface/address would be used.
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        candidate = _valid_ipv4(sock.getsockname()[0])
        if candidate:
            return candidate
    except OSError:
        pass
    finally:
        sock.close()
    try:
        candidate = _valid_ipv4(socket.gethostbyname(socket.gethostname()))
        if candidate:
            return candidate
    except OSError:
        pass
    return "127.0.0.1"

_arg_ip = _valid_ipv4(sys.argv[1]) if len(sys.argv) > 1 else None
LAN_IP = _arg_ip or _autodetect_lan_ipv4()
LAN_IP_SOURCE = "argument" if _arg_ip else ("auto-detected" if LAN_IP != "127.0.0.1" else "loopback fallback")
PYTHON = sys.executable
SMOKE_TEST = "--smoke-test" in sys.argv
MASTER_EXE = ROOT / "ThorGorMasterServer.exe"
CHAT_EXE = ROOT / "ThorGorChatServer.exe"
UDP_EXE = ROOT / "ThorGorUdpShim.exe"
MANAGER_BRIDGE_EXE = ROOT / "ThorGorManagerBridge.exe"
NATIVE_BRIDGE_EXE = ROOT / "ThorGorNativeBridge.exe"

# Keep handles alive for the life of the dashboard. Closing the dashboard does
# not explicitly terminate services, matching the old independent-window model.
PROCS: dict[str, subprocess.Popen] = {}
LOG_HANDLES = []
START_ERRORS: dict[str, str] = {}
VALIDATION_OK = False
VALIDATION_DONE = False

# PyInstaller points the process-wide DLL search directory at its temporary
# extraction folder. External children inherit that setting, which prevents the
# stock HoN slave from resolving game\game_shared.dll while loading game.dll.
_DLL_SEARCH_LOCK = threading.Lock()


@contextlib.contextmanager
def _native_child_dll_search():
    """Give external child processes normal Windows DLL-search semantics."""
    if os.name != "nt" or not IS_FROZEN:
        yield
        return

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    set_dll_directory = kernel32.SetDllDirectoryW
    set_dll_directory.argtypes = [ctypes.c_wchar_p]
    set_dll_directory.restype = ctypes.c_int
    bundled_dir = getattr(sys, "_MEIPASS", None)
    with _DLL_SEARCH_LOCK:
        if not set_dll_directory(None):
            raise OSError(ctypes.get_last_error(), "Could not reset child DLL search path")
        try:
            yield
        finally:
            if bundled_dir:
                set_dll_directory(str(bundled_dir))


def _service_command(executable: Path, script: Path) -> list[str]:
    return [str(executable)] if IS_FROZEN else [PYTHON, str(script)]

def _debug_output_dir() -> Path:
    # Program Files is normally not writable by a non-elevated dashboard.
    # Save uploadable diagnostics somewhere the interactive user always owns.
    desktop = Path(os.environ.get("USERPROFILE", str(ROOT))) / "Desktop" / "ThorGor_Debug_Bundles"
    try:
        desktop.mkdir(parents=True, exist_ok=True)
        test = desktop / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return desktop
    except Exception:
        fallback = Path(os.environ.get("LOCALAPPDATA", os.environ.get("TEMP", str(ROOT)))) / "ThorGor" / "Debug_Bundles"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

DEBUG_DIR = _debug_output_dir()


def _log_handle(name: str):
    f = open(LOG_DIR / f"{name}.log", "a", encoding="utf-8", buffering=1)
    LOG_HANDLES.append(f)
    return f


def launch(name: str, args: list[str], cwd: Path = ROOT) -> None:
    try:
        out = _log_handle(name)
        out.write(f"\n===== dashboard launch {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        out.write("COMMAND: " + subprocess.list2cmdline(args) + "\n\n")
        with _native_child_dll_search():
            PROCS[name] = subprocess.Popen(
                args,
                cwd=str(cwd),
                stdout=out,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=FLAGS,
            )
    except Exception as exc:
        START_ERRORS[name] = str(exc)


def proc_alive(name: str) -> bool:
    p = PROCS.get(name)
    return bool(p is not None and p.poll() is None)


def port_bound(port: int, protocol: str) -> bool:
    """Passively detect a local listener with netstat. Never connects to HoN services."""
    protocol = protocol.lower()
    try:
        r = subprocess.run(
            ["netstat", "-ano", "-p", protocol],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=CREATE_NO_WINDOW,
        )
        for line in r.stdout.splitlines():
            cols = line.split()
            if len(cols) < 2 or cols[0].lower() != protocol:
                continue
            endpoint = cols[1]
            if endpoint.rsplit(":", 1)[-1] != str(port):
                continue
            if protocol == "tcp":
                # TCP status must be a passive LISTENING socket. Do not probe it.
                if any(col.upper() == "LISTENING" for col in cols[2:]):
                    return True
            else:
                return True
    except Exception:
        pass
    return False


def tcp_bound(port: int) -> bool:
    return port_bound(port, "tcp")


def udp_bound(port: int) -> bool:
    return port_bound(port, "udp")


def publication_ready() -> tuple[bool, str]:
    """Read the shared v31/v49 state used by the master to gate CREATE rows."""
    state_path = ROOT / "work" / "v31_registration_state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"state unavailable: {exc}"
    status = state.get("server_status")
    manager_ready = bool(state.get("manager_control_connected") and state.get("manager_associated"))
    chat_ready = bool(state.get("registered") and state.get("chat_server_connected"))
    ready = bool(status in (0, 1) and (manager_ready or chat_ready))
    detail = (
        f"status={status} manager_connected={state.get('manager_control_connected')} "
        f"associated={state.get('manager_associated')} registered={state.get('registered')} "
        f"chat_connected={state.get('chat_server_connected')}"
    )
    return ready, detail


def run_validation() -> None:
    global VALIDATION_OK, VALIDATION_DONE
    try:
        out = _log_handle("health_check")
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(ROOT / "2_CHECK_V45.bat")],
            cwd=str(ROOT),
            stdout=out,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=45,
        )
        VALIDATION_OK = result.returncode == 0
    except Exception as exc:
        START_ERRORS["health_check"] = str(exc)
        VALIDATION_OK = False
    finally:
        VALIDATION_DONE = True


def _run_diag(cmd: list[str], out_path: Path) -> None:
    """Capture a passive diagnostic command without probing game services."""
    try:
        r = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, errors="replace",
            timeout=12, creationflags=CREATE_NO_WINDOW,
        )
        out_path.write_text(
            "COMMAND: " + subprocess.list2cmdline(cmd) + "\n"
            + f"RETURN CODE: {r.returncode}\n\nSTDOUT\n------\n{r.stdout}\n\nSTDERR\n------\n{r.stderr}",
            encoding="utf-8", errors="replace",
        )
    except Exception as exc:
        out_path.write_text(f"FAILED: {exc}\n", encoding="utf-8")


def create_debug_bundle(status_snapshot: dict | None = None) -> Path:
    """Create one uploadable ZIP containing every dashboard/service log and passive host diagnostics."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stage = DEBUG_DIR / f"ThorGor_Debug_{stamp}"
    stage.mkdir(parents=True, exist_ok=True)

    # Flush service streams before copying their files.
    for h in list(LOG_HANDLES):
        try:
            h.flush()
        except Exception:
            pass

    meta = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "lan_ip": LAN_IP,
        "python": sys.executable,
        "hon_home": str(HON_HOME),
        "hon_exe_exists": HON_EXE.is_file(),
        "dashboard_pid": os.getpid(),
        "status": status_snapshot or {},
        "start_errors": START_ERRORS,
        "processes": {k: {"pid": getattr(v, "pid", None), "returncode": v.poll()} for k, v in PROCS.items()},
    }
    (stage / "dashboard_status.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Each ticker's redirected stdout/stderr.
    if LOG_DIR.exists():
        shutil.copytree(LOG_DIR, stage / "dashboard_logs", dirs_exist_ok=True)

    # Project-native logs/state/captures that contain protocol-level evidence.
    wanted_files = [
        ROOT / "thorgor_server_v39.log",
        ROOT / "thorgor_srp_v39.log",
        ROOT / "chat-server" / "thorgor_chat_v13.log",
        ROOT / "work" / "hon_udp_shim_public_list.log",
        ROOT / "work" / "hon_udp_shim_hot_stdout.log",
        ROOT / "work" / "hon_udp_shim_hot_stderr.log",
        ROOT / "work" / "manager_status_bridge_v42.log",
        ROOT / "work" / "manager_status_bridge_v42_events.jsonl",
        ROOT / "work" / "native_matchid_bridge_v47.log",
        ROOT / "work" / "native_matchid_bridge_v47_state.json",
        ROOT / "work" / "v31_registration_state.json",
    ]
    evidence = stage / "runtime_evidence"
    evidence.mkdir(exist_ok=True)
    for src in wanted_files:
        if src.exists() and src.is_file():
            try:
                shutil.copy2(src, evidence / src.name)
            except Exception:
                pass

    for src, output_name in (
        (ROOT / "thorgor_server_v39_captures", "thorgor_server_v39_captures"),
        (ROOT / "thorgor_srp_v39_captures", "thorgor_srp_v39_captures"),
        (ROOT / "chat-server" / "thorgor_chat_v13_captures", "thorgor_chat_v13_captures"),
        (ROOT / "chat-server" / "thorgor_chat_v13_host_captures", "thorgor_chat_v13_host_captures"),
        (ROOT / "work" / "route_traces", "route_traces"),
    ):
        if src.exists():
            try:
                shutil.copytree(src, evidence / output_name, dirs_exist_ok=True)
            except Exception:
                pass

    # Passive machine state only: no TCP connects/pings are performed.
    diag = stage / "machine_state"
    diag.mkdir(exist_ok=True)
    _run_diag(["netstat", "-ano"], diag / "netstat_ano.txt")
    _run_diag(["tasklist", "/v"], diag / "tasklist_v.txt")
    _run_diag(["ipconfig", "/all"], diag / "ipconfig_all.txt")
    _run_diag(["route", "print"], diag / "route_print.txt")
    _run_diag(["powershell.exe", "-NoProfile", "-Command",
               "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine | Format-List"],
              diag / "process_commandlines.txt")
    _run_diag(["powershell.exe", "-NoProfile", "-Command",
               "Get-NetTCPConnection -ErrorAction SilentlyContinue | Sort-Object LocalPort | Format-Table -AutoSize"],
              diag / "tcp_connections.txt")
    _run_diag(["powershell.exe", "-NoProfile", "-Command",
               "Get-NetUDPEndpoint -ErrorAction SilentlyContinue | Sort-Object LocalPort | Format-Table -AutoSize"],
              diag / "udp_endpoints.txt")

    hosts = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    if hosts.exists():
        try:
            shutil.copy2(hosts, diag / "hosts.txt")
        except Exception:
            pass

    zip_path = DEBUG_DIR / f"ThorGor_Debug_{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in stage.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(stage))
    shutil.rmtree(stage, ignore_errors=True)
    return zip_path


class Dashboard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ThorGor HoN 3.2.7.1 - v77 Tail-Recipient Hero Fix")
        self.geometry("690x565")
        self.minsize(620, 515)
        self.configure(bg="#101418")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Panel.TFrame", background="#171d23")
        style.configure("Title.TLabel", background="#101418", foreground="#f2f5f7", font=("Segoe UI", 17, "bold"))
        style.configure("Sub.TLabel", background="#101418", foreground="#9aa7b2", font=("Segoe UI", 9))
        style.configure("Name.TLabel", background="#171d23", foreground="#e5e9ec", font=("Segoe UI", 11))
        style.configure("Info.TLabel", background="#171d23", foreground="#8f9ba6", font=("Segoe UI", 9))
        style.configure("Footer.TLabel", background="#101418", foreground="#86939d", font=("Segoe UI", 9))

        outer = ttk.Frame(self, padding=(22, 18), style="Panel.TFrame")
        outer.pack(fill="both", expand=True, padx=18, pady=(12, 10))

        ttk.Label(self, text="ThorGor HoN v77 Tail-Recipient Hero Fix", style="Title.TLabel").pack(anchor="w", padx=22, pady=(17, 0))
        ttk.Label(self, text=f"Exact v49 native behavior  •  per-client UDP telemetry  •  LAN {LAN_IP} ({LAN_IP_SOURCE})", style="Sub.TLabel").pack(anchor="w", padx=23, pady=(1, 0))

        self.rows: dict[str, tuple[tk.Label, ttk.Label]] = {}
        items = [
            ("master", "Master / Backend", "TCP 80"),
            ("chat", "Chat Server", "TCP 11031"),
            ("udp", "Public UDP Bridge", "UDP 11236"),
            ("backend", "Manager Backend Bridge", "TCP 1135"),
            ("manager", "Original HoN Manager", "TCP 1136"),
            ("dedicated", "Original Dedicated Slave", "UDP 11235"),
            ("publish", "Public Server Ready", "manager association / idle state"),
            ("native", "Native MatchID Bridge", "process"),
            ("health_check", "Startup Health Check", "2_CHECK_V45.bat"),
        ]
        for i, (key, label, detail) in enumerate(items):
            row = ttk.Frame(outer, style="Panel.TFrame")
            row.grid(row=i, column=0, sticky="ew", pady=6)
            row.columnconfigure(1, weight=1)
            icon = tk.Label(row, text="✕", fg="#ff5b63", bg="#171d23", font=("Segoe UI Symbol", 14, "bold"), width=2)
            icon.grid(row=0, column=0, rowspan=2, sticky="w", padx=(2, 10))
            ttk.Label(row, text=label, style="Name.TLabel").grid(row=0, column=1, sticky="w")
            detail_label = ttk.Label(row, text=detail, style="Info.TLabel")
            detail_label.grid(row=1, column=1, sticky="w")
            self.rows[key] = (icon, detail_label)

        self.overall = tk.Label(self, text="STARTING…", fg="#ffc857", bg="#101418", font=("Segoe UI", 10, "bold"))
        self.overall.pack(anchor="w", padx=23)

        buttons = tk.Frame(self, bg="#101418")
        buttons.pack(fill="x", padx=22, pady=(8, 2))
        tk.Button(buttons, text="Open Logs Folder", command=self.open_logs, bg="#27313a", fg="#f2f5f7",
                  activebackground="#34414c", activeforeground="#ffffff", relief="flat", padx=12, pady=6).pack(side="left")
        tk.Button(buttons, text="Create Debug ZIP", command=self.make_debug_zip, bg="#176b49", fg="#ffffff",
                  activebackground="#21885f", activeforeground="#ffffff", relief="flat", padx=12, pady=6).pack(side="left", padx=(8,0))
        self.bundle_status = ttk.Label(self, text=f"Logs: dashboard_logs\\   •   Debug ZIPs: {DEBUG_DIR}", style="Footer.TLabel")
        self.bundle_status.pack(anchor="w", padx=23, pady=(2, 13))

        self.last_statuses = {}
        if SMOKE_TEST:
            self.after(100, self.destroy)
        else:
            self.after(250, self.start_stack)
            self.after(700, self.refresh_status)

    def set_row(self, key: str, ok: bool, detail: str | None = None) -> None:
        icon, detail_label = self.rows[key]
        icon.configure(text="✓" if ok else "✕", fg="#35d07f" if ok else "#ff5b63")
        if detail is not None:
            detail_label.configure(text=detail)

    def open_logs(self) -> None:
        try:
            os.startfile(str(LOG_DIR))
        except Exception as exc:
            self.bundle_status.configure(text=f"Could not open logs folder: {exc}")

    def make_debug_zip(self) -> None:
        self.bundle_status.configure(text="Creating debug ZIP…")
        self.update_idletasks()
        try:
            path = create_debug_bundle(self.last_statuses)
            self.bundle_status.configure(text=f"Created: {path}")
            messagebox.showinfo("ThorGor Debug Bundle", f"Debug ZIP created successfully:\n\n{path}\n\nUpload this ZIP here.")
            try:
                subprocess.Popen(["explorer.exe", "/select,", str(path)])
            except Exception:
                try:
                    os.startfile(str(DEBUG_DIR))
                except Exception:
                    pass
        except Exception as exc:
            err = f"Debug ZIP failed: {exc}"
            self.bundle_status.configure(text=err)
            try:
                (Path(os.environ.get("USERPROFILE", str(ROOT))) / "Desktop" / "ThorGor_DEBUG_ERROR.txt").write_text(err, encoding="utf-8")
            except Exception:
                pass
            messagebox.showerror("ThorGor Debug Bundle Failed", err)

    def start_stack(self) -> None:
        # Exact v49 LAN command arguments and original startup order.
        launch("master", _service_command(MASTER_EXE, ROOT / "thorgor_hon_sandboxed_masterserver_v39.py") + [
            "--host", "0.0.0.0", "--port", "80", "--password-chain", "pre-md5",
            "--chat-host", LAN_IP, "--server-list-ip", LAN_IP, "--server-list-port", "11236",
            "--match-server-ip", "127.0.0.1", "--match-server-port", "11235",
            "--match-server-location", "USE",
        ])
        self.after(2000, self._start_chat)

    def _start_chat(self) -> None:
        launch("chat", _service_command(CHAT_EXE, ROOT / "chat-server" / "thorgor_hon_chatserver_v13.py") + [
            "--host", "0.0.0.0", "--port", "11031",
            "--db", str(ROOT / "thorgor_accounts.db"),
        ], ROOT / "chat-server")
        self.after(2000, self._start_udp)

    def _start_udp(self) -> None:
        launch("udp", _service_command(UDP_EXE, ROOT / "hon_udp_shim.py") + [
            "--preset", "thorgor-public-list",
            "--listen-host", "0.0.0.0", "--listen-port", "11236", "--browser-ip", LAN_IP,
            "--require-c0-auth", "--master-url", "http://127.0.0.1/server_requester.php",
            "--manager-start-timeout", "3", "--max-client-routes", "16",
            "--client-route-timeout", "600", "--stats-interval", "1",
            "--route-trace-seconds", "300", "--route-trace-packets", "40000",
            "--route-trace-checkpoint-seconds", "1",
        ])
        self.after(1000, self._start_backend)

    def _start_backend(self) -> None:
        launch("backend", _service_command(MANAGER_BRIDGE_EXE, ROOT / "hon_manager_status_bridge_v42.py") + [
            "--listen-host", "127.0.0.1", "--listen-port", "1135", "--target-port", "1136",
            "--master-url", "http://127.0.0.1/server_requester.php",
        ])
        self.after(1000, self._start_manager)

    def _start_manager(self) -> None:
        launch("manager", [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(ROOT / "start_manager_v39.ps1"),
            "-HonHome", str(HON_HOME),
        ], HON_HOME)
        self.after(15000, self._start_native)

    def _start_native(self) -> None:
        launch("native", _service_command(NATIVE_BRIDGE_EXE, ROOT / "hon_native_matchid_bridge_v47.py"))
        self.after(1000, self._start_health_check)

    def _start_health_check(self) -> None:
        # Run off the Tk event loop so the status UI stays responsive.
        import threading
        threading.Thread(target=run_validation, daemon=True).start()

    def refresh_status(self) -> None:
        publish_ok, publish_detail = publication_ready()
        statuses = {
            "master": tcp_bound(80),
            "chat": tcp_bound(11031),
            "udp": udp_bound(11236),
            "backend": tcp_bound(1135),
            "manager": tcp_bound(1136),
            "dedicated": udp_bound(11235),
            "publish": publish_ok,
            "native": proc_alive("native"),
            "health_check": VALIDATION_DONE and VALIDATION_OK,
        }

        self.last_statuses = statuses.copy()

        detail_overrides = {
            "master": "TCP 80" + (f"  •  {START_ERRORS['master']}" if "master" in START_ERRORS else ""),
            "chat": "TCP 11031" + (f"  •  {START_ERRORS['chat']}" if "chat" in START_ERRORS else ""),
            "udp": "UDP 11236" + (f"  •  {START_ERRORS['udp']}" if "udp" in START_ERRORS else ""),
            "backend": "TCP 1135" + (f"  •  {START_ERRORS['backend']}" if "backend" in START_ERRORS else ""),
            "manager": "TCP 1136" + (f"  •  {START_ERRORS['manager']}" if "manager" in START_ERRORS else ""),
            "publish": publish_detail,
            "native": "process" + (f"  •  {START_ERRORS['native']}" if "native" in START_ERRORS else ""),
            "health_check": ("2_CHECK_V45.bat  •  passed" if VALIDATION_DONE and VALIDATION_OK else
                             "2_CHECK_V45.bat  •  failed (see log)" if VALIDATION_DONE else
                             "2_CHECK_V45.bat  •  pending"),
        }
        for key, ok in statuses.items():
            self.set_row(key, ok, detail_overrides.get(key))

        core = [statuses[k] for k in ("master", "chat", "udp", "backend", "manager", "dedicated", "publish", "native")]
        if all(core):
            self.overall.configure(text="READY — all runtime components are up", fg="#35d07f")
        elif any(core):
            self.overall.configure(text="STARTING / PARTIAL — waiting for remaining components", fg="#ffc857")
        else:
            self.overall.configure(text="OFFLINE — runtime components not detected", fg="#ff5b63")
        self.after(1500, self.refresh_status)

    def on_close(self) -> None:
        # Always preserve a close-time diagnostic bundle in the project folder
        # BEFORE terminating services. This makes every GUI run leave evidence.
        try:
            generated = create_debug_bundle(getattr(self, "last_statuses", {}))
            local_zip = ROOT / f"ThorGor_SESSION_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            shutil.copy2(generated, local_zip)
        except Exception as exc:
            try:
                (ROOT / f"ThorGor_SESSION_CLOSE_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log").write_text(
                    f"Failed to create close-time diagnostic bundle: {exc}\n", encoding="utf-8"
                )
            except Exception:
                pass

        # The dashboard replaces the old service windows, so closing it must not
        # leave invisible service processes behind. Stop direct children, then
        # run the same project cleanup used before startup.
        for proc in PROCS.values():
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
        try:
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(ROOT / "CLEANUP_OLD_TESTS.ps1")],
                cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW, timeout=8,
            )
        except Exception:
            pass
        for h in list(LOG_HANDLES):
            try:
                h.flush(); h.close()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    Dashboard().mainloop()
