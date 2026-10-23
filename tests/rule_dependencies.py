"""Fingerprint the selected STX import closure, including composed overlays."""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def code_without_literals(source: str) -> str:
    # Preserve line breaks while removing comments, patterns and strings.
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27|`(?:\\.|[^`\\])*`',
        lambda match: '\n'*match.group().count('\n'), source)


def rule_dependencies(seeds: list[Path], directory: Path = ROOT/'dialects') -> list[Path]:
    visited = set()
    pending = [path.resolve() for path in seeds]
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        if not path.is_file():
            raise ValueError('Missing selected rule module: '+str(path))
        visited.add(path)
        code = code_without_literals(path.read_text(encoding='utf-8-sig'))
        for name in re.findall(r'^\s*use\s+([\w.]+)\s*;', code, re.MULTILINE):
            imported = directory.joinpath(*name.split('.')).with_suffix('.stx')
            if not imported.is_file():
                raise ValueError('Missing imported rule module '+name+' from '+str(path))
            pending.append(imported.resolve())
    return sorted(visited)


def c11_rule_inputs() -> list[Path]:
    # The C11 graph, explicit C11 overlays, and the generic allocation/name
    # suites are the selected rules. Other language dialects are not loaded.
    seeds = [*sorted((ROOT/'dialects').glob('c11*.stx')),
        ROOT/'dialects/allocation.stx', ROOT/'dialects/name_scope.stx']
    return [Path(__file__).resolve(), *rule_dependencies(seeds)]
