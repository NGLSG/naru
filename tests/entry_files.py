"""Entry filenames are independent of the selected grammar and raw frontend."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from native_process import execute

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "dialects/base.stx"
FRONTEND = ROOT / "tests/fixtures/entry_frontend.stx"
RAW = "#include <opaque.header>\n@raw source\n"
FILENAMES = ("main.c", "main.C", "main.nru", "main.custom", "main", "入口.c")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target/naru.exe")
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    env = dict(os.environ, PATH="")
    results = []
    with tempfile.TemporaryDirectory(prefix="naru-entry-") as directory:
        work = Path(directory)

        def invoke(command, *options, cwd=None):
            return execute([str(compiler), command, *map(str, options)], cwd=cwd or work, env=env, timeout=90)

        def passed(result):
            assert result.returncode == 0, result.stdout + result.stderr
            return result

        def function(result, value=42):
            output = passed(result).stdout.replace(" ", "")
            assert f'base.Function("main",base.Int({value}))' in output, output

        def check(name, action):
            try:
                action()
                results.append({"name": name, "passed": True})
                print("PASS " + name, flush=True)
            except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
                results.append({"name": name, "passed": False, "error": str(error)})
                print("FAIL " + name + ": " + str(error), flush=True)

        raw_rules = ["--rules", BASE, "--rules", FRONTEND]
        for filename in FILENAMES:
            source = work / filename

            def raw(source=source):
                source.write_text(RAW, encoding="utf-8", newline="\n")
                function(invoke("parse", source, *raw_rules, "--frontend", "entry_frontend.frontend"))

            def ordinary(source=source):
                source.write_text("fn main() -> i32 { return 42; }", encoding="utf-8")
                function(invoke("parse", source, "--rules", BASE))

            check("raw frontend accepts " + filename, raw)
            check("selected ordinary grammar accepts " + filename, ordinary)

        project = work / "project"
        project.mkdir()
        shutil.copy2(FRONTEND, project / "frontend.stx")
        source = project / "main.c"
        source.write_text(RAW, encoding="utf-8", newline="\n")
        (project / "Naru.toml").write_text(
            '[package]\nname="entry-demo"\nversion="0.1.0"\nentry="main.c"\n'
            '[exports]\nentry_frontend="frontend.stx"\n'
            '[dependencies.std]\npath=' + json.dumps(str(ROOT / "dialects")) + '\n'
            '[language]\ndialects=["std/base","entry_frontend"]\n'
            'frontend="entry_frontend.frontend"\nrelation="base.emit_program"\nunit="program"\n'
            '[frontend]\nanswer="42"\n[backend]\ntarget="exe"\n', encoding="utf-8")

        check("project entry main.c from a foreign directory", lambda:
              function(invoke("parse", "--project", project)))
        check("project entry main.c through project discovery", lambda:
              function(invoke("parse", cwd=project)))
        check("CLI frontend overrides the project frontend", lambda:
              function(invoke("parse", "--project", project, "--frontend", "entry_frontend.alternate"), 43))
        check("project frontend receives its configured options", lambda:
              function(invoke("parse", "--project", project, "--frontend", "entry_frontend.configured")))
        check("CLI frontend options override project options", lambda:
              function(invoke("parse", "--project", project, "--frontend", "entry_frontend.configured", "--frontend-option", "answer=43"), 43))

        dependency = project / "helper.payload"
        dependency.write_text("42\n", encoding="utf-8")
        check("frontend reads a dependency with an arbitrary suffix", lambda:
              function(invoke("parse", "--project", project, "--frontend", "entry_frontend.dependency")))

        def input_protection():
            result = invoke("emit", "--project", project, "--frontend", "entry_frontend.dependency", "-o", dependency)
            assert result.returncode == 2 and "overwrite" in result.stdout + result.stderr, result.stdout + result.stderr
            assert dependency.read_text() == "42\n"

        check("a frontend dependency remains protected from output overwrite", input_protection)

        def native():
            output = work / "entry.exe"
            passed(invoke("build", "--project", project, "-o", output))
            ran = execute([str(output)], cwd=work, env=env)
            assert ran.returncode == 42, ran

        check("project main.c builds and runs in process", native)

        def conflict():
            result = invoke("parse", source, *raw_rules, "--rules", ROOT / "tests/fixtures/entry_frontend_conflict.stx",
                            "--frontend", "entry_frontend.frontend")
            assert result.returncode == 1 and "ambiguous effect" in result.stdout + result.stderr, result.stdout + result.stderr

        check("matching frontend rules report ambiguity", conflict)

        def missing():
            result = invoke("parse", work / "absent.c", *raw_rules, "--frontend", "entry_frontend.frontend")
            assert result.returncode == 2 and "source file not found" in result.stdout + result.stderr, result.stdout + result.stderr

        check("missing C entry uses the ordinary missing-input diagnostic", missing)

        def help_text():
            output = passed(invoke("help")).stdout
            assert "<source>" in output and "<file.nru>" not in output, output

        check("CLI help does not require a language-specific suffix", help_text)

    report = {"passed": sum(item["passed"] for item in results), "total": len(results), "checks": results}
    destination = ROOT / "target/entry-file-tests.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{report['passed']}/{report['total']} entry filename checks passed")
    return int(report["passed"] != report["total"])


if __name__ == "__main__":
    raise SystemExit(main())
