"""Deferred C11 VM, bit-field and aligned-member target acceptance.

Uses the shared strict C11/real-CRT reference runner. Importing this module
does not build or execute anything.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    from c11_conformance import main
    raise SystemExit(main(['--probe-manifest', str(ROOT/'tests/c11/vm-layout.json'),
        '--report', str(ROOT/'target/c11-vm-layout.json'), *sys.argv[1:]]))
