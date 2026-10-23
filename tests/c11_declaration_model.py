"""Declaration points, linkage, composite types and old-style function ABI."""
from __future__ import annotations

import sys

from c11_conformance import ROOT, main


if __name__ == '__main__':
    raise SystemExit(main(['--probe-manifest', str(ROOT/'tests/c11/declaration-model.json'),
        '--report', str(ROOT/'target/c11-declaration-model.json'),
        *sys.argv[1:]]))
