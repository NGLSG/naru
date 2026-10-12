"""Launch one Windows process in a Job that prohibits all child processes."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import tempfile
import time


class BasicLimits(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                ("max_working_set", ctypes.c_size_t), ("active_processes", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
                ("reads", "writes", "others", "read_bytes", "write_bytes", "other_bytes")]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", BasicLimits), ("io", IoCounters),
                ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]


class StartupInfo(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("reserved", wintypes.LPWSTR), ("desktop", wintypes.LPWSTR),
                ("title", wintypes.LPWSTR), ("x", wintypes.DWORD), ("y", wintypes.DWORD),
                ("x_size", wintypes.DWORD), ("y_size", wintypes.DWORD), ("x_chars", wintypes.DWORD),
                ("y_chars", wintypes.DWORD), ("fill", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("show", wintypes.WORD), ("reserved_size", wintypes.WORD),
                ("reserved_bytes", ctypes.POINTER(ctypes.c_byte)), ("stdin", wintypes.HANDLE),
                ("stdout", wintypes.HANDLE), ("stderr", wintypes.HANDLE)]


class ProcessInfo(ctypes.Structure):
    _fields_ = [("process", wintypes.HANDLE), ("thread", wintypes.HANDLE),
                ("pid", wintypes.DWORD), ("tid", wintypes.DWORD)]


def execute(arguments: list[str], *, cwd: Path, timeout: float = 120,
            env: dict[str, str] | None = None, memory_limit: int | None = None) -> subprocess.CompletedProcess[str]:
    """A child-process-based compiler necessarily fails under this restriction."""
    if os.name != "nt":
        raise RuntimeError("The no-child-process acceptance test currently requires Windows Job Objects")
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    kernel.QueryInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                      wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
                                      ctypes.POINTER(StartupInfo), ctypes.POINTER(ProcessInfo)]
    kernel.CreateProcessW.restype = wintypes.BOOL
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = ProcessInfo()
    started = time.perf_counter()
    try:
        limits = ExtendedLimits()
        limits.basic.flags = 0x00000008 | 0x00002000  # ACTIVE_PROCESS + KILL_ON_JOB_CLOSE
        limits.basic.active_processes = 1
        if memory_limit is not None:
            if memory_limit < 1:
                raise ValueError("memory_limit must be positive")
            limits.basic.flags |= 0x00000100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
            limits.process_memory = memory_limit
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        with tempfile.TemporaryDirectory(prefix="naru process guard ") as scratch:
            stdout_path, stderr_path = Path(scratch) / "stdout", Path(scratch) / "stderr"
            with open(os.devnull, "rb") as stdin, stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                for stream in (stdin, stdout, stderr):
                    os.set_inheritable(stream.fileno(), True)
                startup = StartupInfo()
                startup.cb = ctypes.sizeof(startup)
                startup.flags = 0x00000100  # STARTF_USESTDHANDLES
                startup.stdin = msvcrt.get_osfhandle(stdin.fileno())
                startup.stdout = msvcrt.get_osfhandle(stdout.fileno())
                startup.stderr = msvcrt.get_osfhandle(stderr.fileno())
                environment = env if env is not None else dict(os.environ)
                env_block = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in
                                                         sorted(environment.items(), key=lambda item: item[0].upper())) + "\0\0")
                command = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments))
                if not kernel.CreateProcessW(arguments[0], command, None, None, True,
                                               0x00000004 | 0x00000400 | 0x08000000,
                                               env_block, str(cwd), ctypes.byref(startup), ctypes.byref(info)):
                    raise ctypes.WinError(ctypes.get_last_error())
                if not kernel.AssignProcessToJobObject(job, info.process):
                    error = ctypes.get_last_error()
                    kernel.TerminateProcess(info.process, 125)
                    raise ctypes.WinError(error)
                if kernel.ResumeThread(info.thread) == 0xFFFFFFFF:
                    raise ctypes.WinError(ctypes.get_last_error())
                waited = kernel.WaitForSingleObject(info.process, max(1, int(timeout * 1000)))
                if waited == 258:
                    kernel.TerminateJobObject(job, 124)
                    kernel.WaitForSingleObject(info.process, 10000)
                    raise subprocess.TimeoutExpired(arguments, timeout)
                if waited != 0:
                    raise ctypes.WinError(ctypes.get_last_error())
                exit_code = wintypes.DWORD()
                if not kernel.GetExitCodeProcess(info.process, ctypes.byref(exit_code)):
                    raise ctypes.WinError(ctypes.get_last_error())
            usage = ExtendedLimits()
            if not kernel.QueryInformationJobObject(job, 9, ctypes.byref(usage), ctypes.sizeof(usage), None):
                raise ctypes.WinError(ctypes.get_last_error())
            result = subprocess.CompletedProcess(arguments, exit_code.value,
                stdout_path.read_text(encoding="utf-8", errors="replace"),
                stderr_path.read_text(encoding="utf-8", errors="replace"))
            result.elapsed_seconds = time.perf_counter() - started
            result.peak_memory_bytes = usage.peak_process_memory
            return result
    finally:
        if info.thread:
            kernel.CloseHandle(info.thread)
        if info.process:
            kernel.CloseHandle(info.process)
        kernel.CloseHandle(job)
