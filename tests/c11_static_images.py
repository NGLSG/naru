"""Deferred symbolic-address static object images and TLS composition contracts."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    from c11_conformance import main
    raise SystemExit(main(['--probe-manifest', str(ROOT/'tests/c11/static-images.json'),
        '--report', str(ROOT/'target/c11-static-images.json'), *sys.argv[1:]]))
