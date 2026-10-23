"""Export the shared MLIR/LLVM support ABI used by native Windows plugins.

Plugins link this backend's import library, not another copy of MLIR's static
libraries. This keeps dialect TypeIDs and the global pass registry shared.
Only a developer build uses Python; the compiler runtime does not.
"""
from pathlib import Path
import argparse
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llvm-root', type=Path, required=True)
    parser.add_argument('--nm', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    components = ('MLIRIR', 'MLIRPass', 'MLIRSupport', 'MLIRTransforms',
                  'MLIRArithDialect', 'MLIRFuncDialect', 'LLVMCore', 'LLVMSupport')
    symbols = {}
    for component in components:
        library = args.llvm_root / 'lib' / (component + '.lib')
        result = subprocess.run([args.nm, '--defined-only', '--extern-only', '--format=posix', str(library)],
                                check=True, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) < 3 or fields[1] not in ('T', 'D', 'B', 'R'):
                continue
            symbol = fields[0]
            if symbol.startswith(('??_C', '??_G', '??_E', '$')):
                continue
            if '@mlir@@' in symbol or '@llvm@@' in symbol or symbol.startswith('LLVM'):
                symbols[symbol] = fields[1] != 'T'
    if len(symbols) > 60000:
        raise RuntimeError('Selected plugin ABI exceeds the PE export limit')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('EXPORTS\n' + '\n'.join('  "' + symbol + '"' + (' DATA' if symbols[symbol] else '')
                          for symbol in sorted(symbols)) + '\n', encoding='utf-8')
    print(f'Plugin ABI: {len(symbols)} shared MLIR/LLVM symbols')


if __name__ == '__main__':
    main()
