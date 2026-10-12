"""C11 layout expression smoke tests (offsetof and declaration alignment)."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import tempfile
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]

CASES = {
    "offsetof and alignof": """
#include <stddef.h>
#include <stdint.h>
struct Data { char tag; uint32_t value; uint64_t count; };
_Static_assert(offsetof(struct Data, value) == 4, "field offset");
_Static_assert(_Alignof(struct Data) == 8, "aggregate alignment");
int main(void) { _Alignas(16) struct Data data; data.value = 42; return data.value; }
""",
    "anonymous member offset": """
#include <stddef.h>
struct Outer { char tag; union { int value; struct { int nested; }; }; };
_Static_assert(offsetof(struct Outer, nested) == 4, "anonymous offset");
int main(void) { return offsetof(struct Outer, nested) == 4 ? 42 : 1; }
""",
    "nested named member offset": """
#include <stddef.h>
struct Inner { char pad; int value; };
struct Outer { char tag; struct Inner inner; };
_Static_assert(offsetof(struct Outer, inner.value) == 8, "nested named offset");
int main(void) { return offsetof(struct Outer, inner.value) == 8 ? 42 : 1; }
""",
    "type-name alignment annotation": """
struct Data { int value; };
int main(void) { _Alignas(struct Data) int value = 42; return value; }
""",
    "object storage alignment": """
#include <stdint.h>
_Alignas(16) int global_value;
int main(void) {
    _Alignas(32) static int static_value;
    _Alignas(16) int local_value;
    uintptr_t g = (uintptr_t)&global_value;
    uintptr_t s = (uintptr_t)&static_value;
    uintptr_t l = (uintptr_t)&local_value;
    return (g % 16 == 0 && s % 32 == 0 && l % 16 == 0) ? 42 : 1;
}
""",
}

INVALID_CASES = {
    "non-power-of-two alignment": "_Alignas(3) int value; int main(void) { return value; }",
    "alignment cannot weaken natural": "_Alignas(2) long long value; int main(void) { return (int)value; }",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target/naru.exe")
    parser.add_argument("--report", type=Path, default=ROOT / "target/c11-layout.json")
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    common = ["--rules", str(ROOT / "dialects/c11.stx"), "--frontend", "c11.frontend",
              "--entry", "c11.item", "--relation", "c11.emit_program", "--unit", "program",
              "--runtime", "crt-static", "--opt-level", "2", "--rule-budget", "100000000",
              "--parse-budget", "100000000"]
    results = []
    with tempfile.TemporaryDirectory(prefix="naru c11 layout ") as directory:
        work = Path(directory)
        for name, source in CASES.items():
            path = work / "main.c"
            output = work / "program.exe"
            path.write_text(source, encoding="utf-8")
            result = {"name": name, "passed": False}
            try:
                build = execute([str(compiler), "build", str(path), *common, "--target", "exe", "-o", str(output)],
                                cwd=work, env=dict(os.environ, PATH=""), timeout=60, memory_limit=2 * 1024**3)
                assert build.returncode == 0, build.stdout + build.stderr
                run = execute([str(output)], cwd=work, timeout=10)
                assert run.returncode == 42, str(run)
                result.update(passed=True, seconds=build.elapsed_seconds, peak_commit_bytes=build.peak_memory_bytes)
            except (AssertionError, OSError) as error:
                result["error"] = str(error)
            results.append(result)
            print(("PASS " if result["passed"] else "FAIL ") + name + ("" if result["passed"] else ": " + result["error"]), flush=True)
        for name, source in INVALID_CASES.items():
            path = work / "invalid.c"
            path.write_text(source, encoding="utf-8")
            result = {"name": name, "passed": False}
            try:
                build = execute([str(compiler), "build", str(path), *common, "--target", "exe", "-o", str(work / "invalid.exe")],
                                cwd=work, env=dict(os.environ, PATH=""), timeout=60, memory_limit=2 * 1024**3)
                assert build.returncode != 0, build.stdout + build.stderr
                result.update(passed=True, seconds=build.elapsed_seconds, peak_commit_bytes=build.peak_memory_bytes)
            except (AssertionError, OSError) as error:
                result["error"] = str(error)
            results.append(result)
            print(("PASS " if result["passed"] else "FAIL ") + name + ("" if result["passed"] else ": " + result["error"]), flush=True)
    passed = sum(item["passed"] for item in results)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"passed": passed, "total": len(results), "results": results}, indent=2) + "\n", encoding="utf-8")
    print(f"{passed}/{len(results)} C11 layout checks passed")
    return int(passed != len(results))


if __name__ == "__main__":
    raise SystemExit(main())
