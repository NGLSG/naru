"""Deferred target aggregate packing and stable translation-time contracts."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    from c11_conformance import main
    raise SystemExit(main(['--probe-manifest', str(ROOT/'tests/c11/packing.json'),
        '--report', str(ROOT/'target/c11-packing.json'), *sys.argv[1:]]))
