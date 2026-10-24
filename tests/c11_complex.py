"""Deferred complex language, storage, ABI and real CRT acceptance.

Reserved Clang constructors/projections supply and inspect imaginary values;
they do not replace the target system complex header or math library.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    from c11_conformance import main
    raise SystemExit(main(['--probe-manifest', str(ROOT/'tests/c11/complex.json'),
        '--report', str(ROOT/'target/c11-complex.json'), *sys.argv[1:]]))
