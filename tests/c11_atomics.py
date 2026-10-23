"""Deferred C11 atomics acceptance. Importing this module does not run checks.

Use a reference compiler supporting C11 and the Clang reserved atomic builtins.
System stdatomic.h integration has its own header acceptance requirements;
the fixture intentionally adds no replacement header or CRT implementation.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    from c11_conformance import main
    raise SystemExit(main(['--probe-manifest', str(ROOT/'tests/c11/atomics.json'),
        '--report', str(ROOT/'target/c11-atomics.json'), *sys.argv[1:]]))
