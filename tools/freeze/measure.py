"""Small interleaved whole-process timing comparison; not a compiler benchmark."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time


def measure(command, cwd):
    start = time.perf_counter_ns()
    result = subprocess.run(command, cwd=cwd, capture_output=True, check=True, timeout=30)
    return (time.perf_counter_ns() - start) / 1_000_000, result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--rules", type=Path, action="append", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--unit", help="Pass --unit to parse/emit (for example program)")
    parser.add_argument("--relation", help="Pass --relation to parse/emit (for example standard.emit_program)")
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.iterations < 3:
        parser.error("--iterations must be at least 3")
    core = str(args.core.resolve())
    frozen = str(args.frozen.resolve())
    source = str(args.source.resolve())
    rules = [part for rule in args.rules for part in ("--rules", str(rule.resolve()))]
    selection = []
    if args.unit:
        selection.extend(("--unit", args.unit))
    if args.relation:
        selection.extend(("--relation", args.relation))
    output = {"platform": platform.platform(), "iterations": args.iterations,
              "scope": "whole subprocess latency, warm filesystem, includes process startup and dialect setup; small smoke measurement, not parser-only speed or throughput",
              "measurements": []}
    with tempfile.TemporaryDirectory(prefix="naru timing ") as cwd:
        for operation in ("parse", "emit"):
            commands = {"dynamic": [core, operation, source, *rules, *selection],
                        "frozen": [frozen, operation, source, *selection]}
            samples = {key: [] for key in commands}
            for _ in range(3):
                for command in commands.values():
                    measure(command, cwd)
            for index in range(args.iterations):
                outcomes = {}
                for key in (("dynamic", "frozen") if index % 2 == 0 else ("frozen", "dynamic")):
                    elapsed, text = measure(commands[key], cwd)
                    samples[key].append(elapsed)
                    outcomes[key] = text
                if outcomes["dynamic"] != outcomes["frozen"]:
                    raise RuntimeError("Refusing to compare timings for different results")
            row = {"operation": operation}
            for key, times in samples.items():
                ordered = sorted(times)
                row[key] = {"median_ms": round(statistics.median(times), 3), "min_ms": round(min(times), 3),
                            "p90_ms": round(ordered[int((len(ordered) - 1) * .9)], 3)}
            output["measurements"].append(row)
            print(json.dumps(row))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
