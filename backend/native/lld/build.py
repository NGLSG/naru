"""Build pinned COFF LLD libraries for embedding in Naru's native backend.

This is a developer build step. Naru links against the resulting libraries and
does not invoke this script or a linker process when compiling user programs.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVISION = "19d3b2d2887ccd8fae4d091dc6c29d6b6d9e2b98"
REPOSITORY = "https://github.com/llvm/llvm-project.git"


def run(arguments: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("argv: " + json.dumps(arguments), flush=True)
    subprocess.run(arguments, cwd=cwd, env=env, check=True)


def msvc_environment() -> dict[str, str]:
    finder = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if not finder.is_file():
        raise RuntimeError("Visual Studio installer vswhere.exe was not found")
    installation = subprocess.check_output([str(finder), "-latest", "-products", "*", "-requires",
                                            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], text=True).strip()
    vcvars = Path(installation) / "VC/Auxiliary/Build/vcvars64.bat"
    if not vcvars.is_file():
        raise RuntimeError("Visual Studio x64 C++ build tools were not found")
    command_processor = os.environ.get("COMSPEC", "cmd.exe")
    # cmd.exe has a distinct quoting convention; list2cmdline would escape the
    # batch file's quotes with backslashes, which cmd treats as literal bytes.
    output = subprocess.check_output(f'"{command_processor}" /d /s /c ""{vcvars}" >nul && set"',
                                     text=True, errors="replace")
    environment = dict(os.environ)
    for line in output.splitlines():
        if "=" in line and not line.startswith("="):
            key, value = line.split("=", 1)
            environment[key] = value
    return environment


def source_checkout(source: Path) -> None:
    if not (source / ".git").exists():
        if source.exists() and any(source.iterdir()):
            raise RuntimeError(f"Refusing to replace a nonempty source directory: {source}")
        run(["git", "clone", "--filter=blob:none", "--no-checkout", "--depth=1", REPOSITORY, str(source)])
        run(["git", "sparse-checkout", "set", "lld", "cmake"], cwd=source)
        run(["git", "fetch", "--depth=1", "origin", REVISION], cwd=source)
        run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=source)
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if actual != REVISION:
        raise RuntimeError(f"LLD source revision is {actual}, expected {REVISION}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llvm-root", type=Path, default=ROOT / ".tools/mlir/toolchain/llvm-install")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    llvm_root = args.llvm_root.resolve()
    source = HERE / "source"
    output = HERE / "build"
    installed_revision = (llvm_root / "include/llvm/Support/VCSRevision.h").read_text(encoding="utf-8")
    if REVISION not in installed_revision:
        raise RuntimeError("Installed LLVM revision does not match pinned LLD source")
    source_checkout(source)
    environment = msvc_environment()
    compiler = shutil.which("clang-cl", path=environment.get("PATH"))
    cmake = shutil.which("cmake", path=environment.get("PATH"))
    ninja = shutil.which("ninja", path=environment.get("PATH"))
    if not compiler or not cmake or not ninja:
        raise RuntimeError("clang-cl, cmake and ninja must be installed")
    command = [cmake, "-S", (source / "lld").as_posix(), "-B", output.as_posix(), "-G", "Ninja",
               "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_C_COMPILER=" + Path(compiler).as_posix(),
               "-DCMAKE_CXX_COMPILER=" + Path(compiler).as_posix(), "-DCMAKE_MAKE_PROGRAM=" + Path(ninja).as_posix(),
               "-DLLVM_DIR=" + (llvm_root / "lib/cmake/llvm").as_posix(),
               "-DLLVM_INCLUDE_TESTS=OFF", "-DLLVM_INCLUDE_DOCS=OFF", "-DLLD_BUILD_TOOLS=OFF",
               "-DLLVM_ENABLE_ASSERTIONS=ON", "-DLLVM_ENABLE_RTTI=ON", "-DLLVM_ENABLE_EH=OFF",
               "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded"]
    run(command, env=environment)
    run([cmake, "--build", str(output), "--target", "lldCOFF", "lldCommon", "--parallel", str(args.jobs)], env=environment)
    libraries = [output / "lib/lldCOFF.lib", output / "lib/lldCommon.lib"]
    if not all(path.is_file() for path in libraries):
        raise RuntimeError("LLD build did not produce both required libraries")
    record = {
        "revision": REVISION,
        "repository": REPOSITORY,
        "llvm_root": str(llvm_root),
        "include_directories": [str(source / "lld/include"), str(output / "include")],
        "libraries": [str(path) for path in libraries],
        "runtime": "MultiThreaded",
        "assertions": True,
        "rtti": True,
    }
    (HERE / "libraries.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"LLD library build: {error}", file=sys.stderr)
        sys.exit(1)
