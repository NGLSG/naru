"""Prepare the SDK's std/logger package for the Windows Naru build."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REVISION = '27cb4c76708608465c413f6d0e6b8d99a4d84302'
sys.path.insert(0, str(ROOT.parents[1]/'tools'))
from vyx_sdk import resolve_sdk


def run(arguments: list[str]) -> None:
    print('[std/logger] ' + subprocess.list2cmdline(arguments), flush=True)
    subprocess.run(arguments, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 64:
        parser.error('--jobs must be 1..64')
    args.sdk = resolve_sdk(args.sdk)
    dci = args.sdk/'tools/dci/dci.py'
    if not dci.is_file():
        parser.error(f'Missing SDK DCI tools: {dci}')
    compiler = shutil.which('clang++.exe')
    if not compiler:
        parser.error('clang++.exe is required to prepare std/logger')
    source = ROOT/'vendor/spdlog'
    build = ROOT/'vendor/build'
    contract = ROOT/'contracts/spdlog.dcib'
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        run(['git', 'clone', '--depth', '1', '--branch', 'v1.14.1',
             'https://github.com/gabime/spdlog.git', str(source)])
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise ValueError(f'spdlog revision mismatch: expected {REVISION}, got {revision}')
    run(['cmake', '-S', str(source), '-B', str(build), '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
         f'-DCMAKE_CXX_COMPILER={compiler}', '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded',
         '-DSPDLOG_BUILD_EXAMPLE=OFF', '-DSPDLOG_BUILD_TESTS=OFF', '-DSPDLOG_BUILD_SHARED=OFF'])
    run(['cmake', '--build', str(build), '--parallel', str(args.jobs)])
    inputs = [ROOT/'native/spdlog_dci.hpp', source/'include/spdlog/sinks/sink.h',
              source/'include/spdlog/details/log_msg.h', source/'include/spdlog/formatter.h',
              source/'include/spdlog/logger.h']
    fingerprint = {'revision': revision, 'compiler': compiler, 'triplet': 'windows_x64',
                   'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    stamp = contract.with_suffix('.inputs.json')
    if not contract.is_file() or not stamp.is_file() or json.loads(stamp.read_text()) != fingerprint:
        contract.parent.mkdir(parents=True, exist_ok=True)
        run([sys.executable, str(dci), 'adapter', '--language', 'cpp',
             *map(str, inputs), '--toolchain', 'clang', '--compiler', compiler,
             '--triplet', 'windows_x64', '--jobs', str(args.jobs),
             '--cmake_build_path', str(build), '-o', str(contract)])
        stamp.write_text(json.dumps(fingerprint, indent=2)+'\n', encoding='utf-8')
    print('[std/logger] Windows spdlog library and DCI contract ready', flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('[std/logger] '+str(error), file=sys.stderr)
        raise SystemExit(1)
