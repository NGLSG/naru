"""C11 tag identity, declaration points and enumerator scope acceptance."""
from pathlib import Path
import sys

from c11_conformance import main

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    raise SystemExit(main([
        '--probe-manifest', str(root / 'tests/c11/tag-scopes.json'),
        '--report', str(root / 'target/c11-tags.json'),
        *sys.argv[1:],
    ]))
