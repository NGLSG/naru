"""Deferred target aggregate alignment and actual setjmp/longjmp acceptance."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    from c11_conformance import main
    raise SystemExit(main(['--probe-manifest', str(ROOT/'tests/c11/system-control.json'),
        '--report', str(ROOT/'target/c11-system-control.json'), *sys.argv[1:]]))
