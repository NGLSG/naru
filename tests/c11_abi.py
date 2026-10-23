"""Deferred C11 Windows x64 ABI acceptance; no checks run when imported."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    from c11_conformance import main
    raise SystemExit(main(['--probe-manifest', str(ROOT/'tests/c11/abi.json'),
        '--report', str(ROOT/'target/c11-abi.json'), *sys.argv[1:]]))
