"""Clause-tagged declaration specifiers against an independent C11 compiler."""
from pathlib import Path
import sys
from c11_conformance import main

ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    raise SystemExit(main(['--probe-manifest',str(ROOT/'tests/c11/specifiers.json'),
        '--report',str(ROOT/'target/c11-specifiers.json'),*sys.argv[1:]]))
