"""Reject stale or unfinished frozen projects before claiming rule parity."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_frozen(compiler: Path, *, core: Path, required_rules: list[Path]) -> dict:
    compiler = compiler.resolve()
    project = compiler.parent.parent
    marker = project / 'naru-frozen-project.json'
    if not marker.is_file():
        raise ValueError(f'Frozen provenance manifest missing: {marker}')
    info = json.loads(marker.read_text(encoding='utf-8'))
    if 'build_metrics' not in info or Path(info.get('executable', '')).resolve() != compiler:
        raise ValueError('Frozen build is unfinished or its executable does not match the manifest')
    if info['core_sha256'] != digest(core):
        raise ValueError('Frozen generator differs from the current core; rebuild before claiming parity')
    generated = project / 'src/specialized.vyx'
    if info['specialization_sha256'] != digest(generated):
        raise ValueError('Frozen generated source changed after generation')
    rules = {Path(item['path']).resolve(): item['sha256'] for item in info['rules']}
    if any(rule.resolve() not in rules for rule in required_rules):
        raise ValueError('Frozen compiler lacks a required rule module')
    for path, sha256 in rules.items():
        if digest(path) != sha256:
            raise ValueError(f'Frozen rules differ from the current input: {path}')
    backend = compiler.parent / 'naru_mlir_backend.dll'
    if info['backend']['sha256'] != digest(backend):
        raise ValueError('Frozen backend changed after deployment')
    executable_hash = digest(compiler)
    if info.get('executable_sha256', executable_hash) != executable_hash:
        raise ValueError('Frozen executable changed after the build')
    return {'manifest': str(marker), 'manifest_sha256': digest(marker),
        'compiler_opt_level': info.get('compiler_opt_level'),
        'core_sha256': info['core_sha256'], 'rules': info['rules'],
        'generated_source_sha256': info['specialization_sha256'],
        'backend_sha256': info['backend']['sha256'], 'executable_sha256': executable_hash,
        'build_recorded_executable_hash': 'executable_sha256' in info}
