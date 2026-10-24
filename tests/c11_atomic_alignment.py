"""Deferred atomic alignment, shared protocol and typed lock-free query gates."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    from c11_conformance import main
    raise SystemExit(main(['--probe-manifest', str(ROOT/'tests/c11/atomic-alignment.json'),
        '--report', str(ROOT/'target/c11-atomic-alignment.json'), *sys.argv[1:]]))
