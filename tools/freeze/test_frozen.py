"""Compare an actual AOT-specialized compiler with the dynamic core compiler."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def execute(argv: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--rules", type=Path, action="append", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    core = str(args.core.resolve())
    frozen = str(args.frozen.resolve())
    rule_args = []
    for rule in args.rules:
        rule_args.extend(["--rules", str(rule.resolve())])
    cases = [
        ("lazy-else", ["eval", "--expr", "freeze_semantics.lazy(0)"], 0),
        ("lazy-then", ["eval", "--expr", "freeze_semantics.lazy(1)"], 0),
        ("sequence", ["eval", "--expr", "freeze_semantics.sequence(41)"], 0),
        ("capture-equality", ["eval", "--expr", "freeze_semantics.repeated(freeze_semantics.Pair(4, 4))"], 0),
        ("capture-mismatch", ["eval", "--expr", "freeze_semantics.repeated(freeze_semantics.Pair(4, 5))"], 1),
        ("ambiguity", ["eval", "--expr", "freeze_semantics.overlap(1)"], 1),
        ("recursion", ["eval", "--expr", "freeze_semantics.count(20)"], 0),
        ("rule-error", ["eval", "--expr", "freeze_semantics.bad()"], 1),
        ("region-evaluation", ["eval", "--expr", "freeze_semantics.nested_region()"], 0),
        ("native-mlir-emission", ["emit", str(ROOT / "examples" / "answer.nru")], 0),
    ]
    results = []
    # A different working directory ensures the frozen compiler cannot load
    # the project's Naru.toml implicitly to mask a missing embedded grammar.
    with tempfile.TemporaryDirectory(prefix="naru frozen checks ") as scratch:
        for name, options, expected in cases:
            dynamic = execute([core, *options, *rule_args])
            native = execute([frozen, *options], Path(scratch))
            same = dynamic.returncode == native.returncode == expected and dynamic.stdout == native.stdout and dynamic.stderr == native.stderr
            record = {"test": name, "passed": same, "dynamic_exit": dynamic.returncode, "frozen_exit": native.returncode}
            if not same:
                record.update({"dynamic_stdout": dynamic.stdout, "frozen_stdout": native.stdout,
                               "dynamic_stderr": dynamic.stderr, "frozen_stderr": native.stderr})
            results.append(record)
            print(("PASS " if same else "FAIL ") + name)
            if not same:
                print(json.dumps(record, indent=2))
    report = {"passed": all(case["passed"] for case in results), "cases": results}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
