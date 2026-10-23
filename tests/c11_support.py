"""Run pending-feature probes without converting missing support into a pass.

This uses the clause acceptance runner and its reference, native process and
artifact guards. It is intentionally an explicit, initially failing baseline.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


if __name__ == '__main__':
    from c11_conformance import main
    raise SystemExit(main(['--probe-manifest', str(ROOT / 'tests/c11/support-probes.json'),
        '--report', str(ROOT / 'target/c11-support.json'), *sys.argv[1:]]))
