#!/usr/bin/env python3
"""Compare user-facing parse trees and diagnostics of dynamic and frozen compilers."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from run import ROOT


def invoke(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=30)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, default=ROOT / "target" / "naru.exe")
    parser.add_argument("--base", type=Path, default=ROOT / "target" / "specialized-base" / "target" / "naru.exe")
    parser.add_argument("--ownership", type=Path, default=ROOT / "target" / "specialized-ownership" / "target" / "naru.exe")
    args = parser.parse_args()
    for path in (args.core, args.base, args.ownership):
        if not path.is_file():
            parser.error(f"compiler does not exist: {path}; build the specialized compilers first")
    cases = [
        ("operator precedence parse tree", "base", "parse", "tests/fixtures/precedence.nru", 0, []),
        ("parenthesized parse tree", "base", "parse", "tests/fixtures/parentheses.nru", 0, []),
        ("malformed source diagnostic", "base", "check", "tests/fixtures/malformed.nru", 1, []),
        ("unknown suffix diagnostic", "base", "check", "tests/fixtures/trailing_unknown.nru", 1, []),
        ("source-module diamond parse tree", "base", "parse", "tests/fixtures/source_modules/diamond.nru", 0, []),
        ("ownership branch success", "ownership", "check", "examples/ownership/branch_valid.nru", 0, ["--relation", "analyze"]),
        ("ownership branch failure diagnostic", "ownership", "check", "examples/ownership/branch_invalid.nru", 1, ["--relation", "analyze"]),
        ("unless extension parse tree", "ownership", "parse", "examples/ownership/unless_valid.nru", 0, []),
        ("unless extension failure diagnostic", "ownership", "check", "examples/ownership/unless_invalid.nru", 1, ["--relation", "analyze"]),
        ("user-defined loop fixed-point success", "ownership", "check", "examples/ownership/loop_valid.nru", 0, ["--relation", "analyze"]),
        ("user-defined loop iteration failure diagnostic", "ownership", "check", "examples/ownership/loop_invalid.nru", 1, ["--relation", "analyze"]),
    ]
    failures = 0
    with tempfile.TemporaryDirectory(prefix="naru parity ") as directory:
        cwd = Path(directory)
        for name, group, command, source, expected, extra in cases:
            rules = ["dialects/base.stx"] if group == "base" else ["dialects/ownership.stx", "dialects/unless.stx", "dialects/loops.stx"]
            rule_args = [argument for rule in rules for argument in ("--rules", str(ROOT / rule))]
            common = [command, str(ROOT / source), *extra]
            dynamic = invoke([str(args.core.resolve()), *common, *rule_args], cwd)
            native = invoke([str(getattr(args, group).resolve()), *common], cwd)
            same = dynamic.returncode == native.returncode == expected \
                and dynamic.stdout == native.stdout and dynamic.stderr == native.stderr
            print(f"{'PASS' if same else 'FAIL'} {name}")
            if not same:
                failures += 1
                print(f"dynamic exit={dynamic.returncode}\n{dynamic.stdout}{dynamic.stderr}")
                print(f"frozen exit={native.returncode}\n{native.stdout}{native.stderr}")
    print(f"\n{len(cases) - failures}/{len(cases)} dynamic/AOT parity checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
