"""Build a frozen Naru compiler with native Vyx effect implementations.

The Naru executable generates code; this script only stages and invokes Vyx.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SDK = Path("E:/Dev/C++/VyxLan-selfhost-yolo/dist/vyx-sdk-windows-x86_64-llvm22")


def process_tree_commit(root_pid: int) -> int:
    """Sample only this build's process tree, including compiler workers."""
    if os.name != "nt":
        return 0
    class ProcessEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                    ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
                    ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent", wintypes.DWORD), ("priority", wintypes.LONG),
                    ("flags", wintypes.DWORD), ("exe", wintypes.WCHAR * 260)]
    class MemoryCounters(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("peak_ws", "ws", "peak_paged", "paged",
                                                "peak_nonpaged", "nonpaged", "commit", "peak_commit", "private")]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32FirstW.restype = kernel.Process32NextW.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    parents = {}
    try:
        entry = ProcessEntry(); entry.size = ctypes.sizeof(entry)
        present = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while present:
            parents[entry.pid] = entry.parent
            present = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    owned = {root_pid}
    while True:
        expanded = owned | {pid for pid, parent in parents.items() if parent in owned}
        if expanded == owned:
            break
        owned = expanded
    total = 0
    for pid in owned:
        handle = kernel.OpenProcess(0x410, False, pid)
        if not handle:  # A worker can exit between snapshot and query.
            continue
        try:
            counters = MemoryCounters(); counters.size = ctypes.sizeof(counters)
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.size):
                total += counters.private
        finally:
            kernel.CloseHandle(handle)
    return total


def execute(command: list[str], cwd: Path) -> dict:
    print("argv: " + json.dumps(command, ensure_ascii=False), flush=True)
    started = time.perf_counter(); peak = 0; sampling_errors = []
    with subprocess.Popen(command, cwd=cwd, shell=False) as process:
        while process.poll() is None:
            try:
                peak = max(peak, process_tree_commit(process.pid))
            except OSError as error:
                # A low-memory process snapshot must not convert a successful
                # compiler exit into a build failure. Keep the gap explicit.
                sampling_errors.append(getattr(error, 'winerror', None) or error.errno)
            try:
                process.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                pass
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command)
    return {"seconds": time.perf_counter() - started,
            "peak_sampled_tree_private_commit_bytes": peak if os.name == "nt" and peak else None,
            "memory_sample_interval_seconds": 0.25,
            "memory_sample_failure_count": len(sampling_errors),
            "memory_sampling_complete": not sampling_errors if os.name == "nt" else None,
            "memory_sample_error_codes": sorted(set(code for code in sampling_errors if code is not None))}


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def stage_backend(destination: Path, executable: Path, core: Path) -> dict:
    """Ship the in-process backend beside the new compiler, with no CLI tools."""
    bridge = core.parent / "naru_mlir_backend.dll"
    if not bridge.is_file():
        raise ValueError(f"Native MLIR backend is missing beside the core compiler: {bridge}")
    deployed = executable.parent / bridge.name
    shutil.copy2(bridge, deployed)
    backend = destination / "backend"
    backend.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / "backend").glob("*-target.json"):
        shutil.copy2(source, backend / source.name)
    examples = ROOT / "backend" / "examples"
    if examples.is_dir():
        shutil.copytree(examples, backend / "examples", dirs_exist_ok=True)
    # These directories were produced by previous versions of this same build
    # script. The caller has already checked the frozen-project ownership marker.
    for relative in ("tools/mlir", ".tools/mlir"):
        legacy = (destination / relative).resolve()
        if not legacy.is_relative_to(destination) or legacy == destination:
            raise ValueError(f"Legacy cleanup escaped the frozen project: {legacy}")
        if legacy.is_dir():
            shutil.rmtree(legacy)
    return {"mode": "in-process", "library": str(deployed), "sha256": digest(deployed),
            "source_library": str(bridge), "external_toolchain_required": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True, help="Existing core Naru executable")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--rules", type=Path, action="append")
    selection.add_argument("--project", type=Path, help="Project whose complete dialect group is frozen")
    parser.add_argument("--locked", action="store_true", help="Require the project's existing Naru.lock")
    parser.add_argument("--compiler-opt-level", choices=("0", "1", "2", "3"), default="2",
                        help="Vyx optimization of the compiler itself; independent of generated-program optimization")
    parser.add_argument("--jobs", type=int, default=4, help="Vyx build worker count (1..64, default 4)")
    parser.add_argument("--output", type=Path, required=True, help="New compiler project directory")
    parser.add_argument("--sdk", type=Path, default=Path(os.environ.get("VYX_SDK", str(DEFAULT_SDK))))
    args = parser.parse_args()
    if not 1 <= args.jobs <= 64:
        parser.error("--jobs must be between 1 and 64")
    core = args.core.resolve()
    sdk = args.sdk.resolve()
    destination = args.output.resolve()
    compiler = sdk / "bin" / "vyxc.exe"
    rules = [rule.resolve() for rule in args.rules or []]
    project = args.project.resolve() if args.project else None
    if project and project.is_dir():
        project = project / "Naru.toml"
    if args.locked and not project:
        raise ValueError("--locked requires --project")
    for path in [core, compiler, *rules, *([project] if project else [])]:
        if not path.is_file():
            raise ValueError(f"Required file does not exist: {path}")
    # Do not overwrite the source checkout or an unrelated directory. Rebuilds
    # are permitted only in a directory previously owned by this script.
    marker = destination / "naru-frozen-project.json"
    if destination == ROOT or ROOT.is_relative_to(destination):
        raise ValueError("Frozen output must not contain the source checkout")
    if destination.exists() and any(destination.iterdir()) and not marker.is_file():
        raise ValueError(f"Output directory is nonempty and is not a frozen project: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    source_dir = destination / "src"
    source_dir.mkdir(exist_ok=True)
    for source in (ROOT / "src").iterdir():
        if source.is_file() and source.name != "specialized.vyx":
            shutil.copy2(source, source_dir / source.name)
    shutil.copy2(ROOT / "Vyx.toml", destination / "Vyx.toml")
    generated = source_dir / "specialized.vyx"
    command = [str(core), "freeze", "-o", str(generated)]
    if project:
        command.extend(["--project", str(project)])
    if args.locked:
        command.append("--locked")
    for rule in rules:
        command.extend(["--rules", str(rule)])
    execute(command, ROOT)
    generated_text = generated.read_text(encoding="utf-8")
    # Read module path records from the generated artifact. These are
    # the complete linked module set, including imports discovered by Naru;
    # hashing only the command-line --rules list would miss dependencies.
    literal_paths = re.findall(r'^// frozen module: ("(?:\\.|[^"\\])*")$', generated_text, re.MULTILINE)
    if not literal_paths:  # Older core compilers emit direct initializer calls.
        literal_paths = re.findall(r'e\.modules\.push\(ModuleInfo \{ path: ("(?:\\.|[^"\\])*"), name:', generated_text)
    linked_rules = sorted({Path(json.loads(value)).resolve() for value in literal_paths})
    if not linked_rules:
        raise ValueError("Generated specialization has no linked rule modules")
    for path in linked_rules:
        if not path.is_file():
            raise ValueError(f"Cannot fingerprint a linked rule module: {path}")
    # An ownership manifest also records the exact generated implementation.
    info = {
        "format": 1,
        "core": str(core),
        "core_sha256": digest(core),
        "sdk": str(sdk),
        "vyxc_sha256": digest(compiler),
        "compiler_opt_level": args.compiler_opt_level,
        "build_jobs": args.jobs,
        "explicit_rules": [str(rule) for rule in rules],
        "project": str(project) if project else None,
        "project_lock_sha256": digest(project.parent / "Naru.lock") if project else None,
        "rules": [{"path": str(rule), "sha256": digest(rule)} for rule in linked_rules],
        "specialization_sha256": digest(generated),
        "effect_execution": "native Vyx pattern checks and RHS functions",
        "surface_parser": "native unrolled syntax matchers with shared Pratt precedence dispatch",
    }
    marker.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    artifact_record = destination / "artifact.txt"
    info["build_metrics"] = execute([str(compiler), "build", "--target", "naru", "--artifact-file", str(artifact_record), "-j" + str(args.jobs), "-O" + args.compiler_opt_level], destination)
    info["generated_source_bytes"] = generated.stat().st_size
    executable = Path(artifact_record.read_text(encoding="utf-8-sig").strip())
    if not executable.is_file():
        raise ValueError(f"Vyx did not produce its reported executable: {executable}")
    info["executable"] = str(executable)
    info["backend"] = stage_backend(destination, executable, core)
    marker.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(executable)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("naru freeze build: " + str(error), file=sys.stderr)
        sys.exit(1)
