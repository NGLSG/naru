"""Project packages, lock files and in-process native linking acceptance tests."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from native_process import execute

ROOT = Path(__file__).resolve().parents[1]


def put(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def package(path: Path, name: str, extra: str = "", version: str = "0.2.3") -> Path:
    return put(path / "Naru.toml", f'[package]\nname = "{name}"\nversion = "{version}"\n' + extra)


def stdlib(path: Path) -> None:
    # Exact copies also allow the frozen image to validate a relocated project.
    shutil.copytree(ROOT / "dialects", path, ignore=shutil.ignore_patterns("__pycache__", "target"))


def app(path: Path, dialects: str = '"std/base", "std/externc"', extra: str = "",
        program: str = "fn main() -> i32 { return 42; }") -> Path:
    stdlib(path / "std")
    put(path / "main.nru", program)
    return package(path, "project-test",
        'entry = "main.nru"\n[dependencies]\n'
        'std = { path = "std", package = "naru-stdlib", version = "^0.2.0" }\n'
        '[language]\ndialects = [' + dialects + ']\nrelation = "base.emit_program"\nunit = "program"\n'
        '[backend]\ntarget = "exe"\nopt_level = 2\n' + extra)


def graph(path: Path, requirement: str = "^0.2.0") -> Path:
    package(path / "leaf", "leaf", '[exports]\nhelper = "impl/number.stx"\n')
    put(path / "leaf/impl/number.stx", 'mod helper; effect value() => 42;')
    package(path / "middle", "middle", '[dependencies.leaf]\npath = "../leaf"\n'
        f'version = "{requirement}"\n[exports]\nfacade = "rules/api.stx"\n')
    put(path / "middle/rules/api.stx", 'mod facade; use helper; effect answer() => helper.value();')
    return package(path, "graph-root", '[dependencies]\nmid = { path = "middle" }\n'
        'direct = { path = "leaf" }\n[language]\ndialects = ["mid/facade"]\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target/naru.exe")
    parser.add_argument("--frozen", action="store_true")
    parser.add_argument("--cc", default=shutil.which("clang"))
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    env = dict(os.environ, PATH="")
    for name in ("NARU_MLIR_BACKEND", "LIB", "VCToolsInstallDir", "WindowsSdkDir", "WindowsSDKVersion"):
        env.pop(name, None)
    checks = 0
    failures = []
    with tempfile.TemporaryDirectory(prefix="naru project 中文 ") as directory:
        scratch = Path(directory)
        foreign = scratch / "foreign"
        foreign.mkdir()

        def invoke(command, *options, cwd=None):
            return execute([str(compiler), command, *map(str, options)], cwd=cwd or foreign, env=env)

        def success(result):
            assert result.returncode == 0, result.stdout + result.stderr
            return result

        def reject(result, message):
            assert result.returncode in (1, 2), f"crash/unexpected status {result.returncode}: {result.stdout}{result.stderr}"
            assert message in result.stdout + result.stderr, result.stdout + result.stderr

        def check(label, body):
            nonlocal checks
            checks += 1
            case = scratch / f"case {checks}"
            case.mkdir()
            try:
                body(case)
                print("PASS " + label, flush=True)
            except (AssertionError, OSError, ValueError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
                failures.append(label)
                print("FAIL " + label + ": " + str(error), flush=True)

        def build_default(path, nested=False):
            app(path)
            cwd = path / "src/nested" if nested else path
            cwd.mkdir(parents=True, exist_ok=True)
            # Frozen compilers deliberately require --project; ordinary frozen
            # invocations retain their existing fixed-group, projectless mode.
            options = ["--project", path] if args.frozen else []
            success(invoke("build", *options, cwd=cwd))
            binary = path / "target/project-test.exe"
            assert execute([str(binary)], cwd=foreign, env=env).returncode == 42
            assert (path / "Naru.lock").is_file()

        check("default source/output and composed base + externc project", build_default)
        check("explicit project from a nested directory" if args.frozen else "ancestor discovery from a nested directory",
            lambda p: build_default(p, True))

        def lock_hashes(path):
            app(path)
            result = success(invoke("resolve", "--project", path))
            lock = json.loads(result.stdout)
            assert json.loads((path / "Naru.lock").read_text()) == lock
            for section, field in (("packages", "manifest"), ("rules", "path")):
                for item in lock[section]:
                    assert not Path(item[field]).is_absolute()
                    assert hashlib.sha256((path / item[field]).read_bytes()).hexdigest() == item["sha256"]
            assert [rule["module"] for rule in lock["rules"]] == ["base", "externc", "numbers", "pipeline", "types"]
            old = (path / "Naru.lock").read_bytes()
            success(invoke("build", "--project", path, "--locked"))
            assert (path / "Naru.lock").read_bytes() == old

        check("SHA256 lock records and locked build from another cwd", lock_hashes)

        def crt(path, runtime):
            app(path, extra=f'[link]\nruntime = "{runtime}"\n', program=
                'extern "C" { fn puts(text: *char) -> i32; }\n'
                'fn main() -> i32 { let n: i32 = puts("automatic native linking"); if n < 0 { return 1; } return 42; }')
            report = path / "report.json"
            success(invoke("build", "--project", path, "--report", report))
            actual = execute([str(path / "target/project-test.exe")], cwd=foreign, env=env)
            assert actual.returncode == 42 and actual.stdout.strip() == "automatic native linking", actual
            data = json.loads(report.read_text())
            assert data["processes_spawned"] == 0 and data["link"]["runtime"] == runtime
            assert len(data["link"]["libraries"]) == 5
            assert data["link"]["vc_tools_dir"] and data["link"]["windows_sdk_version"]

        check("static CRT discovery and puts with no PATH/child processes", lambda p: crt(p, "crt-static"))
        check("dynamic CRT discovery and puts with no PATH/child processes", lambda p: crt(p, "crt-dynamic"))

        def crt_overrides(path):
            app(path, extra='[link]\nruntime = "crt-static"\n')
            report = path / "report.json"
            success(invoke("build", "--project", path, "--report", report))
            discovered = json.loads(report.read_text())["link"]
            success(invoke("build", "--project", path, "--vc-tools-dir", discovered["vc_tools_dir"],
                "--windows-sdk-dir", discovered["windows_sdk_dir"], "--windows-sdk-version", discovered["windows_sdk_version"],
                "--report", report))
            actual = json.loads(report.read_text())["link"]
            assert actual["libraries"] == discovered["libraries"]
            assert execute([str(path / "target/project-test.exe")], cwd=foreign, env=env).returncode == 42

        check("explicit MSVC/SDK configuration repeats discovered linking", crt_overrides)

        def source_changes(path):
            app(path)
            success(invoke("resolve", "--project", path))
            put(path / "main.nru", 'fn main() -> i32 { return 43; }')
            success(invoke("build", "--project", path, "--locked"))
            assert execute([str(path / "target/project-test.exe")], cwd=foreign, env=env).returncode == 43

        check("source edits do not invalidate dependency lock", source_changes)

        def frozen_failure(path, mutation, message):
            app(path)
            success(invoke("resolve", "--project", path))
            mutation(path)
            reject(invoke("build", "--project", path), message)

        if args.frozen:
            check("frozen project rejects changed selected dialect", lambda p: frozen_failure(p,
                lambda q: put(q / "std/externc.stx", (q / "std/externc.stx").read_text() + "\n// drift\n"),
                "differs from this frozen compiler"))
            check("frozen project rejects changed transitive dialect", lambda p: frozen_failure(p,
                lambda q: put(q / "std/numbers.stx", (q / "std/numbers.stx").read_text() + "\n// drift\n"),
                "differs from frozen dialect"))
            check("frozen image rejects a smaller selected group", lambda p: frozen_failure(p,
                lambda q: put(q / "Naru.toml", (q / "Naru.toml").read_text().replace(', "std/externc"', '')),
                "different dialect group"))
            check("identical explicit rules reuse the frozen module", lambda p:
                (app(p), success(invoke("build", "--project", p, "--rules", p / "std/base.stx"))))
        else:
            def graph_resolve(path):
                graph(path)
                data = json.loads(success(invoke("resolve", "--project", path)).stdout)
                assert len(data["packages"]) == 3 and len(data["dependencies"]) == 3
                assert {rule["module"] for rule in data["rules"]} == {"helper", "facade"}
                assert success(invoke("eval", "--project", path, "--expr", "facade.answer()")).stdout.strip() == "42"

            check("transitive project exports, diamond dedup and qualified relation", graph_resolve)

            def rule_package(path):
                graph(path)
                data = json.loads(success(invoke("resolve", "--project", path / "middle")).stdout)
                assert len(data["packages"]) == 2 and data["rules"] == []
                success(invoke("resolve", "--project", path / "middle", "--locked"))

            check("rule package resolves dependencies without an application grammar", rule_package)

            def own_export(path):
                package(path, "own-export", '[exports]\nlocal = "rules.stx"\n[language]\ndialects = ["local"]\n')
                put(path / "rules.stx", 'mod local; effect answer() => 42;')
                assert success(invoke("eval", "--project", path, "--expr", "local.answer()")).stdout.strip() == "42"

            check("project can reference its own exported dialect", own_export)

            def composition(path):
                app(path, dialects='"std/base", "std/ownership", "std/resources", "std/standard"',
                    program=(ROOT / "tests/fixtures/composed.nru").read_text())
                manifest = path / "Naru.toml"
                put(manifest, manifest.read_text().replace('relation = "base.emit_program"', 'relation = "standard.emit_program"'))
                success(invoke("build", "--project", path))
                assert execute([str(path / "target/project-test.exe")], cwd=foreign, env=env).returncode == 42

            check("project selects base + ownership + resources with an aggregate relation", composition)

            for requirement in ("0.2.3", "^0.2.0", "~0.2.1", "*"):
                check("accepted version " + requirement, lambda p, r=requirement:
                    (graph(p, r), success(invoke("resolve", "--project", p))))
            for requirement in ("0.2.2", "^0.1.0", "~0.1.9", "^0.0.3", "^1.0.0", ">=0.2.0"):
                check("rejected version " + requirement, lambda p, r=requirement:
                    (graph(p, r), reject(invoke("resolve", "--project", p), "version mismatch")))

            def graph_reject(path, mutation, message):
                graph(path)
                mutation(path)
                reject(invoke("resolve", "--project", path), message)

            check("cycles are diagnosed", lambda p: graph_reject(p, lambda q: package(q / "leaf", "leaf",
                '[dependencies]\nroot = { path = ".." }\n'), "dependency cycle"))
            check("same package identity at different paths is diagnosed", lambda p: graph_reject(p,
                lambda q: package(q / "middle", "leaf"), "conflicting package identity"))
            check("unknown dependency alias is diagnosed", lambda p: graph_reject(p,
                lambda q: put(q / "Naru.toml", (q / "Naru.toml").read_text().replace("mid/facade", "absent/facade")),
                "unknown project dependency"))
            check("unknown dialect export is diagnosed", lambda p: graph_reject(p,
                lambda q: put(q / "Naru.toml", (q / "Naru.toml").read_text().replace("mid/facade", "mid/absent")),
                "unknown dialect export"))
            check("declared module must match its export", lambda p: graph_reject(p,
                lambda q: put(q / "middle/rules/api.stx", 'mod renamed; effect answer() => 42;'),
                "declares module 'renamed'"))
            check("missing dependency manifests are diagnosed", lambda p: graph_reject(p,
                lambda q: (q / "leaf/Naru.toml").unlink(), "cannot read text input"))
            check("missing exported STX files are diagnosed", lambda p: graph_reject(p,
                lambda q: (q / "leaf/impl/number.stx").unlink(), "existing .stx"))
            check("expected package name is validated", lambda p: graph_reject(p,
                lambda q: put(q / "Naru.toml", (q / "Naru.toml").read_text().replace('path = "middle"', 'path = "middle", package = "wrong"')),
                "package name mismatch"))
            check("conflicting export identity is diagnosed", lambda p: graph_reject(p,
                lambda q: package(q / "middle", "middle", '[exports]\nhelper = "rules/api.stx"\n'),
                "conflicting dialect export"))

            for text, message in (
                ('[package]\nname = "../escape"\nversion = "0.1.0"\n', "invalid package name"),
                ('[package]\nname = "test"\nversion = "01.2.3"\n', "major.minor.patch"),
                ('[package]\nname = "test"\nname = "duplicate"\n', "duplicate project key"),
                ('[package]\nname = "test"\n[package]\n', "duplicate project section"),
                ('[language]\ndialects = "std/base"\n', "expected '['"),
                ('[unknown]\nvalue = "test"\n', "unsupported project section"),
                ('[backend]\nunknown = "test"\n', "unsupported project key"),
            ):
                check("manifest validation: " + message, lambda p, t=text, m=message:
                    (put(p / "Naru.toml", t), reject(invoke("resolve", "--project", p), m)))

            def lock_reject(path, change=None):
                app(path)
                if change:
                    success(invoke("resolve", "--project", path))
                    change(path)
                before = (path / "Naru.lock").read_bytes() if (path / "Naru.lock").exists() else None
                reject(invoke("build", "--project", path, "--locked"), "missing or out of date")
                after = (path / "Naru.lock").read_bytes() if (path / "Naru.lock").exists() else None
                assert before == after

            check("locked build rejects missing lock without writing it", lock_reject)
            check("locked build rejects changed manifest", lambda p: lock_reject(p,
                lambda q: put(q / "std/Naru.toml", (q / "std/Naru.toml").read_text() + "\n# changed\n")))
            check("locked build rejects changed transitive rule", lambda p: lock_reject(p,
                lambda q: put(q / "std/numbers.stx", (q / "std/numbers.stx").read_text() + "\n// changed\n")))
            check("locked build rejects changed lock data", lambda p: lock_reject(p,
                lambda q: put(q / "Naru.lock", (q / "Naru.lock").read_text().replace('"format": 1', '"format": 2'))))

            def lock_whitespace(path):
                app(path)
                success(invoke("resolve", "--project", path))
                put(path / "Naru.lock", json.dumps(json.loads((path / "Naru.lock").read_text()), separators=(",", ":")))
                success(invoke("build", "--project", path, "--locked"))

            check("lock formatting may change without semantic drift", lock_whitespace)

            def relocate(path):
                app(path / "before")
                success(invoke("resolve", "--project", path / "before"))
                shutil.copytree(path / "before", path / "after")
                success(invoke("build", "--project", path / "after", "--locked"))

            check("project and packages relocate with their lock", relocate)

            def protected(path, target, report=False, alias=False):
                app(path)
                success(invoke("resolve", "--project", path))
                input_path = path / target
                before = input_path.read_bytes()
                output = path / "alias" if alias else input_path
                if alias:
                    os.link(input_path, output)
                flags = ["--report", output, "-o", path / "result.exe"] if report else ["-o", output]
                reject(invoke("build", "--project", path, *flags), "overwrite")
                assert before == input_path.read_bytes()

            for target in ("Naru.toml", "Naru.lock", "std/Naru.toml", "std/numbers.stx", "std/ownership.stx"):
                check("protect project input " + target, lambda p, t=target: protected(p, t))
            check("protect lock file through a hardlink report alias", lambda p: protected(p, "Naru.lock", True, True))

            def override(path):
                app(path, extra='[link]\nruntime = "not-a-runtime"\n')
                report = path / "report.json"
                success(invoke("build", "--project", path, "--runtime", "freestanding", "--opt-level", "0", "--report", report))
                data = json.loads(report.read_text())
                assert data["link"]["runtime"] == "freestanding" and data["opt_level"] == "0"

            check("CLI overrides project scalar settings", override)

            def link_failure(path, options, message, report_required=True):
                app(path)
                binary = put(path / "result.exe", "existing artifact")
                report = path / "report.json"
                reject(invoke("build", "--project", path, "-o", binary, "--report", report, *options), message)
                assert binary.read_text() == "existing artifact"
                if report_required:
                    assert json.loads(report.read_text())["success"] is False

            check("missing library reports failure and preserves artifact", lambda p: link_failure(p,
                ["--link-library", "naru-nonexistent-library"], "link library not found"))
            check("missing object reports failure and preserves artifact", lambda p: link_failure(p,
                ["--link-object", str(p / "missing.obj")], "link object not found"))
            check("library names cannot inject linker options", lambda p: link_failure(p,
                ["--link-library", "@response"], "library name", False))

            def native_input(path, library=False, protect=False, profile=False, duplicate=False):
                assert args.cc, "Clang is required only to prepare the independent object fixture"
                source = put(path / "native.c", "int foreign_answer(void) { return 42; }")
                obj = path / "native.obj"
                prepared = subprocess.run([args.cc, "-c", "-O2", "-fno-stack-protector", str(source), "-o", str(obj)],
                    capture_output=True, text=True, timeout=60)
                success(prepared)
                input_path = obj
                if library:
                    lib = path / "native.lib"
                    librarian = Path(args.cc).parent / "llvm-lib.exe"
                    success(subprocess.run([str(librarian), f"/out:{lib}", str(obj)], capture_output=True, text=True, timeout=60))
                    input_path = lib
                app(path / "app", extra='', program='extern "C" { fn foreign_answer() -> i32; }\nfn main() -> i32 { return foreign_answer(); }')
                # Link inputs contributed by a dependency project; paths are
                # relative to that dependency, independent of the caller cwd.
                if library:
                    extra = '[link]\nlibraries = ["native"]\nlibrary_paths = [".."]\n'
                else:
                    extra = '[link]\nobjects = ["../native.obj"]\n'
                package(path / "native-package", "native-package", extra)
                manifest = path / "app/Naru.toml"
                put(manifest, manifest.read_text().replace('[dependencies]\n', '[dependencies]\nnative = { path = "../native-package" }\n'))
                report = path / "report.json"
                flags = []
                if profile:
                    # Target JSON inputs are relative to that JSON, not cwd.
                    put(path / "target-profile.json", json.dumps({"artifact": "exe", "link_objects": ["native.obj"]}))
                    flags = ["--target", path / "target-profile.json"]
                if duplicate:
                    alias = path / "native alias.obj"
                    os.link(obj, alias)
                    flags += ["--link-object", alias]
                if protect:
                    before = input_path.read_bytes()
                    alias = path / "alias.exe"
                    os.link(input_path, alias)
                    reject(invoke("build", "--project", path / "app", "-o", alias), "overwrite")
                    assert input_path.read_bytes() == before
                else:
                    output = path / "result.exe"
                    success(invoke("build", "--project", path / "app", "-o", output, "--report", report, *flags))
                    assert execute([str(output)], cwd=foreign, env=env).returncode == 42
                    data = json.loads(report.read_text())
                    assert data["processes_spawned"] == 0
                    assert len(data["link"]["libraries" if library else "objects"]) == 1

            check("dependency project contributes a native object", native_input)
            check("dependency project contributes named library/search path", lambda p: native_input(p, True))
            check("object hardlink cannot be overwritten", lambda p: native_input(p, False, True))
            check("resolved library hardlink cannot be overwritten", lambda p: native_input(p, True, True))
            check("target profile resolves and deduplicates project link objects", lambda p: native_input(p, profile=True))
            check("same physical link object through hardlinks is passed once", lambda p: native_input(p, duplicate=True))

    print(f"{checks - len(failures)}/{checks} project/link checks passed")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
