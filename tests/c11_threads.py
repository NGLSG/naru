"""Deferred C11 thread, synchronization, TLS and atomic environment acceptance.

Every thread and synchronization interface comes from the actual installed
MSVC headers and runtime. This file does not provide a substitute threads.h.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    from c11_conformance import main
    raise SystemExit(main(['--probe-manifest', str(ROOT/'tests/c11/threads.json'),
        '--report', str(ROOT/'target/c11-threads.json'), *sys.argv[1:]]))
