"""Record the real target header policy and expose selected files to Clang.

The overlay changes only the independent reference compiler's search path.
It points at installed, unmodified headers; it never supplies header text or
participates in Naru compilation. All execution is deferred to suite invocation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

from native_process import execute


@dataclass
class HeaderPolicy:
    target: dict
    directories: list[str]
    exclusions: dict[str, list[str]]
    case_sensitive: bool

    def key(self, path: str) -> str:
        result = Path(path).resolve().as_posix()
        return result if self.case_sensitive else result.casefold()

    def find(self, header: str) -> Path | None:
        name = header if self.case_sensitive else header.casefold()
        excluded = {self.key(path) for path in self.exclusions.get(name, [])}
        return next((Path(root)/header for root in self.directories
                     if root and self.key(root) not in excluded
                     and (Path(root)/header).is_file()), None)

    def origin(self, header: str) -> dict | None:
        path = self.find(header)
        return None if path is None else {
            'path': str(path.resolve()),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        }


def discover(compiler: Path, rules: list[str], root: Path) -> HeaderPolicy:
    query = ('bind($o,c11.pp.configure(env.empty()),'
             '[env.entries(env.get($o,"target_facts")),'
             'env.get($o,"system_include_paths"),'
             'env.entries(headers.option($o,"header_exclusions",env.empty())),'
             'headers.option($o,"header_path_case_sensitive",1)])')
    found = execute([str(compiler), 'eval', *rules, '--expr', query],
                    cwd=root, env=dict(os.environ, PATH=''), timeout=20)
    if found.returncode:
        raise RuntimeError('C11 target header discovery: '+found.stdout+found.stderr)
    target, directories, exclusions, sensitive = json.loads(found.stdout)
    return HeaderPolicy(dict(target), directories, dict(exclusions), bool(sensitive))


def reference_view(folder: Path, policy: HeaderPolicy,
                   headers: tuple[str, ...] = ('tgmath.h',)) -> tuple[list[str], dict]:
    virtual = (folder/'reference-header-view').resolve()
    virtual.mkdir()
    files = []
    origins = {}
    for header in headers:
        if Path(header).name != header:
            raise ValueError('Reference header view requires a simple header name')
        origin = policy.origin(header)
        if origin is None:
            raise RuntimeError('Actual target header is missing: '+header)
        origins[header] = origin
        files.append({'type': 'file', 'name': header,
                      'external-contents': Path(origin['path']).as_posix()})
    descriptor = {'version': 0, 'case-sensitive': policy.case_sensitive,
                  'use-external-names': True,
                  'roots': [{'type': 'directory', 'name': virtual.as_posix(),
                             'contents': files}]}
    overlay = folder/'reference-headers.json'
    overlay.write_text(json.dumps(descriptor, indent=2)+'\n', encoding='utf-8')
    return ['-ivfsoverlay', str(overlay), '-I', str(virtual)], {
        'scope': 'independent Clang only; installed unmodified target headers',
        'descriptor': descriptor, 'origins': origins,
    }


def unchanged(view: dict) -> bool:
    return all(Path(origin['path']).is_file() and
               hashlib.sha256(Path(origin['path']).read_bytes()).hexdigest() == origin['sha256']
               for origin in view.get('origins', {}).values())
