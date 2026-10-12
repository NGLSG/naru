#!/usr/bin/env python3
"""Source-module loading contracts, independent of rule-package imports."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from run import BASE, Case, ROOT, qualified, run_case, source

FIXTURES = "tests/fixtures/source_modules/"


CASES = [
    Case("diamond imports occur once, before dependents, in stable order",
         source("parse", FIXTURES + "diamond.nru", BASE),
         tree=qualified("base", '[Function("common_value",Int(3)),Function("left_value",Int(1)),Function("right_value",Int(2)),Function("main",Int(42))]')),
    Case("qualified import resolves a nested source path", source("parse", FIXTURES + "nested_root.nru", BASE),
         tree=qualified("base", '[Function("nested_value",Int(7)),Function("main",Int(42))]')),
    Case("source import cycles are diagnosed", source("check", FIXTURES + "cycle_a.nru", BASE), False,
         contains=("cycle",)),
    Case("imported module declaration must match its requested name", source("check", FIXTURES + "mismatch_root.nru", BASE), False,
         contains=("mismatch",)),
    Case("imported files must declare a module", source("check", FIXTURES + "no_decl_root.nru", BASE), False),
    Case("two imported files cannot claim the same module", source("check", FIXTURES + "duplicate_root.nru", BASE), False,
         contains=("shared",)),
    Case("source imports must remain in the header", source("check", FIXTURES + "late_use.nru", BASE), False,
         contains=("use",)),
    Case("module declaration must precede program items", source("check", FIXTURES + "late_mod.nru", BASE), False,
         contains=("mod",)),
    Case("program imports cannot activate unselected syntax", source("check", FIXTURES + "extra_syntax_root.nru", BASE), False,
         contains=("extra_syntax",)),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target" / "naru.exe")
    args = parser.parse_args()
    failures = 0
    for case in CASES:
        failure = run_case(args.compiler.resolve(), case, 15.0)
        print(f"{'FAIL' if failure else 'PASS'} {case.name}")
        if failure:
            print(failure)
            failures += 1
    print(f"\n{len(CASES) - failures}/{len(CASES)} source-module tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
