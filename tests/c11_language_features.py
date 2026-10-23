"""Deferred C11 function, TLS, parameter-array and character acceptance batch.

Uses the shared clause runner, real CRT and independent reference. Each extra
translation unit is compiled by Naru itself. No execution is performed when
this module is imported.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


if __name__ == '__main__':
    from c11_conformance import main
    raise SystemExit(main(['--probe-manifest', str(ROOT/'tests/c11/language-features.json'),
        '--report', str(ROOT/'target/c11-language-features.json'), *sys.argv[1:]]))
