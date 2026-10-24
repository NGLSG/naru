"""Find a caller-supplied Vyx SDK without a developer-machine fallback."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def resolve_sdk(explicit: str | Path | None = None, *, root: Path = ROOT) -> Path:
    configured = explicit or os.environ.get('VYX_SDK_ROOT') or os.environ.get('VYX_SDK')
    if configured:
        sdk = Path(configured).expanduser().resolve()
        if not (sdk/'bin/vyxc.exe').is_file():
            raise ValueError(f'Vyx SDK has no bin/vyxc.exe: {sdk}')
        return sdk
    compiler = shutil.which('vyxc.exe')
    if compiler:
        return resolve_sdk(Path(compiler).resolve().parent.parent, root=root)
    for name in ('vyx-sdk', 'vyx-sdk-windows-x86_64-llvm22'):
        sdk = root/'.tools'/name
        if (sdk/'bin/vyxc.exe').is_file():
            return sdk.resolve()
    raise ValueError('Vyx SDK not found. Pass -VyxSdk/--sdk, set VYX_SDK_ROOT, '
                     'or put the SDK bin directory on PATH. See docs/building.md.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path)
    args = parser.parse_args()
    try:
        print(resolve_sdk(args.sdk))
    except ValueError as error:
        parser.exit(1, str(error)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
