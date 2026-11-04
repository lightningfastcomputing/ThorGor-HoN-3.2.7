"""Own a suspended Windows process and all its descendants."""
import ctypes as C
from ctypes import wintypes as W
import subprocess
import _winapi as win
import time


class BasicLimits(C.Structure):
    _fields_ = [
        ("process_time", C.c_int64), ("job_time", C.c_int64), ("flags", W.DWORD),
        ("min_working_set", C.c_size_t), ("max_working_set", C.c_size_t),
        ("active_processes", W.DWORD), ("affinity", C.c_size_t),
        ("priority", W.DWORD), ("scheduling", W.DWORD),
    ]


class ExtendedLimits(C.Structure):
    _fields_ = [
        ("basic", BasicLimits), ("io_counters", C.c_uint64 * 6),
        ("memory_limits_and_peaks", C.c_size_t * 4),
    ]


class ProcessList(C.Structure):
    _fields_ = [("assigned", W.DWORD), ("count", W.DWORD), ("pids", C.c_size_t * 32)]


class ProcessEntry(C.Structure):
    _fields_ = [
        ("size", W.DWORD), ("usage", W.DWORD), ("pid", W.DWORD),
        ("heap", C.c_size_t), ("module", W.DWORD), ("threads", W.DWORD),
        ("parent", W.DWORD), ("priority", W.LONG), ("flags", W.DWORD),
        ("executable", W.WCHAR * 260),
    ]


kernel = C.WinDLL("kernel32", use_last_error=True)
for name, args, result in (
    ("CreateJobObjectW", (C.c_void_p, W.LPCWSTR), W.HANDLE),
    ("SetInformationJobObject", (W.HANDLE, C.c_int, C.c_void_p, W.DWORD), W.BOOL),
    ("AssignProcessToJobObject", (W.HANDLE, W.HANDLE), W.BOOL),
    ("QueryInformationJobObject", (W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p), W.BOOL),
    ("TerminateJobObject", (W.HANDLE, W.UINT), W.BOOL),
    ("ResumeThread", (W.HANDLE,), W.DWORD),
    ("CreateToolhelp32Snapshot", (W.DWORD, W.DWORD), W.HANDLE),
    ("Process32FirstW", (W.HANDLE, C.POINTER(ProcessEntry)), W.BOOL),
    ("Process32NextW", (W.HANDLE, C.POINTER(ProcessEntry)), W.BOOL),
):
    function = getattr(kernel, name)
    function.argtypes = args
    function.restype = result


def running_hon():
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == C.c_void_p(-1).value:
        raise C.WinError(C.get_last_error())
    try:
        entry = ProcessEntry()
        entry.size = C.sizeof(entry)
        found = kernel.Process32FirstW(snapshot, C.byref(entry))
        while found:
            if entry.executable.casefold() == "hon.exe":
                return True
            found = kernel.Process32NextW(snapshot, C.byref(entry))
        return False
    finally:
        win.CloseHandle(snapshot)


class NativeJob:
    def __init__(self, command, cwd, env):
        self.job = kernel.CreateJobObjectW(None, None)
        if not self.job:
            raise C.WinError(C.get_last_error())
        self.handles = {}
        try:
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE
            if not kernel.SetInformationJobObject(self.job, 9, C.byref(limits), C.sizeof(limits)):
                raise C.WinError(C.get_last_error())
            process, thread, self.pid, _ = win.CreateProcess(
                command[0], '"' + command[0] + '" ' + subprocess.list2cmdline(command[1:]),
                None, None, False,
                0x4 | subprocess.CREATE_NO_WINDOW, env, str(cwd), subprocess.STARTUPINFO(),
            )
            self.handles[self.pid] = process
            try:
                if not kernel.AssignProcessToJobObject(self.job, process):
                    raise C.WinError(C.get_last_error())
                if kernel.ResumeThread(thread) == 0xFFFFFFFF:
                    raise C.WinError(C.get_last_error())
            except BaseException:
                win.TerminateProcess(process, 1)
                win.WaitForSingleObject(process, 5000)
                raise
            finally:
                win.CloseHandle(thread)
        except BaseException:
            self.close()
            raise

    def pids(self):
        info = ProcessList()
        if not kernel.QueryInformationJobObject(self.job, 3, C.byref(info), C.sizeof(info), None):
            raise C.WinError(C.get_last_error())
        return set(info.pids[:info.count])

    def track(self, pid):
        if pid not in self.pids():
            raise RuntimeError("native process is outside the test job")
        if pid not in self.handles:
            self.handles[pid] = win.OpenProcess(0x100000 | 0x1000, False, pid)

    def stop(self):
        try:
            for pid in self.pids():
                self.track(pid)
            if not kernel.TerminateJobObject(self.job, 1):
                raise C.WinError(C.get_last_error())
            for handle in self.handles.values():
                if win.WaitForSingleObject(handle, 5000) != win.WAIT_OBJECT_0:
                    raise TimeoutError("native process did not exit")
            deadline = time.monotonic() + 5
            while self.pids():
                if time.monotonic() >= deadline:
                    raise TimeoutError("native job still owns live processes")
                time.sleep(0.05)
            return {pid: win.GetExitCodeProcess(handle) for pid, handle in self.handles.items()}
        finally:
            self.close()

    def close(self):
        win.CloseHandle(self.job)
        for handle in self.handles.values():
            win.CloseHandle(handle)
