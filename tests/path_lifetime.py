#!/usr/bin/env python3
"""Vyx/CRT boundary regression: borrowed slices, ownership, allocator reuse."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

# This driver needs only the lexer/model/linker components. No semantic rule is
# evaluated; the stub satisfies project.vyx's otherwise unreachable dependency.
DRIVER = r'''
public fn builtin_name(name: string) -> bool { return false; }

extern "C" { fn memset(pointer: rawptr, value: i32, count: i64) -> rawptr; }

public fn main() -> i32 {
    let expected = naru_absolute_path("dialects/base.stx");
    if (expected.len == 0) { println("empty normalized path"); return 1; }

    // A slice ends before the sentinel, but its backing buffer does not.
    let backing = "dialects/base.stxSENTINEL_MUST_NOT_BE_READ";
    let sliced = from_cstr_view_len(backing.c_str(), 17);
    if (naru_absolute_path(sliced) != expected) {
        println("CRT consumed bytes beyond the input slice"); return 2;
    }

    var retained = Vec::<string>.new();
    var i: i64 = 0;
    while (i < 1024) {
        retained.push(naru_absolute_path(sliced));
        // Reuse recently freed allocator buckets before checking retained paths.
        let churn = calloc(512, 1);
        if (churn == null) { return 3; }
        memset(churn, 88, 511);
        free(churn);
        i = i + 1;
    }
    i = 0;
    while (i < retained.len) {
        if (retained.get(i) != expected) {
            println("normalized path retained a freed CRT buffer"); return 4;
        }
        i = i + 1;
    }

    var invalid = StringBuilder.create();
    invalid.append("dialects/base.stx");
    invalid.appendChar(0);
    invalid.append("ignored");
    let invalid_owned = invalid.build();
    if (naru_absolute_path(invalid_owned.as_str()).len != 0) {
        println("embedded NUL accepted"); return 5;
    }
    let fixture_dir = getArg(1);
    var empty_engine = Engine.new();
    let empty = naru_read_text(&mut empty_engine, naru_join_path(fixture_dir, "empty.nru"));
    if (!empty_engine.good() || empty.len != 0) {
        println("empty text file misread: " + empty_engine.diagnostic); return 6;
    }
    var rule_engine = Engine.new();
    if (load_rule_file(&mut rule_engine, naru_join_path(fixture_dir, "nul.stx"))
        || rule_engine.diagnostic.indexOf("NUL") < 0) {
        println("NUL rule suffix silently truncated"); return 7;
    }
    var source_engine = Engine.new();
    naru_read_text(&mut source_engine, naru_join_path(fixture_dir, "nul.nru"));
    if (source_engine.good() || source_engine.diagnostic.indexOf("NUL") < 0) {
        println("NUL source suffix silently truncated"); return 8;
    }
    var missing_engine = Engine.new();
    naru_read_text(&mut missing_engine, naru_join_path(fixture_dir, "missing.nru"));
    if (missing_engine.good()) { println("missing input accepted as empty"); return 9; }
    println("PASS path slice and CRT ownership regression (1024 retained paths)");
    println("PASS length-preserving input, embedded NUL, empty and missing files");
    return 0;
}
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vyx-sdk", type=Path,
                        default=Path(r"E:\Dev\C++\VyxLan-selfhost-yolo\dist\vyx-sdk-windows-x86_64-llvm22"))
    args = parser.parse_args()
    compiler = args.vyx_sdk / "bin" / "vyxc.exe"
    if not compiler.is_file():
        parser.error(f"Vyx compiler not found: {compiler}")
    fragments = []
    for name in ("model", "lex", "stx", "project"):
        contents = (ROOT / "src" / f"{name}.vyx").read_text(encoding="utf-8-sig")
        for declaration in ("module naru;", "use std.collections;", "use std.string;", "use std.fs;"):
            contents = contents.replace(declaration, "")
        fragments.append(contents)
    with tempfile.TemporaryDirectory(prefix="naru-path-lifetime-") as directory:
        folder = Path(directory)
        (folder / "empty.nru").write_bytes(b"")
        (folder / "nul.stx").write_bytes(b"mod safe; syntax item `ok` => Safe();\x00unparsed garbage")
        (folder / "nul.nru").write_bytes(b"fn main() -> i32 { return 42; }\x00unparsed garbage")
        source = folder / "regression.vyx"
        source.write_text("module lifetimecheck;\nuse std.collections; use std.string; use std.fs;\n"
                          + "\n".join(fragments) + DRIVER, encoding="utf-8")
        for level in ("-O0", "-O2"):
            executable = folder / f"regression{level}.exe"
            result = subprocess.run([str(compiler), "--src=file", str(source), "-o", str(executable), level],
                                    cwd=ROOT, timeout=120)
            if result.returncode:
                return result.returncode
            result = subprocess.run([str(executable), str(folder)], cwd=ROOT, timeout=30)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
