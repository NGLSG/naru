"""Check and export a reviewable Naru source preview; never publish or alter Git history."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[2]
VERSION = '0.2.0-preview.1'
ROOT_FILES = {'.gitignore', '.gitattributes', '.editorconfig', 'LICENSE', 'LICENSE-MIT',
              'LICENSE-APACHE', 'NOTICE', 'THIRD_PARTY.md', 'README.md', 'README.en.md',
              'CONTRIBUTING.md', 'SECURITY.md', 'Vyx.toml', 'Naru.toml', 'Naru.lock',
              'build.ps1', 'naru.ps1', 'package.ps1', 'test.ps1'}
DIRECTORIES = {'.github', 'src', 'dialects', 'backend', 'runtime', 'tools', 'tests',
               'docs', 'examples', 'benchmarks', 'packages', 'registry', 'templates',
               'historical'}
GENERATED = {'.git', '.cache', '.tools', '.naru', '__pycache__', 'node_modules', 'target', 'dist'}
PREFIXES = ('backend/native/build/', 'backend/native/lld/build/', 'backend/native/lld/source/',
            'packages/vyx-logger/vendor/', 'packages/vyx-logger/contracts/',
            'packages/vyx-logger/out/')
BINARY = {'.exe', '.dll', '.obj', '.o', '.lib', '.pdb', '.exp', '.ilk', '.zip', '.gz', '.7z', '.log'}
PRIVATE_NAME = re.compile(r'(^\.env(?:\..*)?$|\.(?:pem|key|pfx|p12)$|^id_(?:rsa|ed25519)$)', re.I)
SECRET = re.compile(rb'-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{36,}\b')
REQUIRED = ('LICENSE', 'LICENSE-MIT', 'LICENSE-APACHE', 'NOTICE', 'THIRD_PARTY.md',
            'README.md', 'README.en.md', 'CONTRIBUTING.md', 'SECURITY.md',
            'docs/building.md', 'docs/status.md', 'docs/release.md', 'Vyx.toml')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selected(relative: PurePosixPath) -> bool:
    name = relative.as_posix()
    if any(part in GENERATED for part in relative.parts) or name.startswith(PREFIXES):
        return False
    if relative.suffix.lower() in BINARY or relative.name.endswith(('.local.json', '.local.toml')):
        return False
    if relative.parts[0] == 'historical':
        return relative.name in {'INDEX.md', 'notes.md', 'README.md', 'source-preview.json'}
    return name in ROOT_FILES or relative.parts[0] in DIRECTORIES


def collect(root: Path) -> tuple[list[Path], list[str]]:
    root = root.resolve()
    if (root/'.git').exists():
        listed = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z',
                                         '--cached', '--others', '--exclude-standard'])
        names = sorted(set(listed.decode('utf-8').strip('\0').split('\0')))
    else:
        names = sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file())
    files, originals = [], []
    for name in names:
        if not name:
            continue
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe source path: '+name)
        if PRIVATE_NAME.search(relative.name) and relative.name != '.env.example':
            raise ValueError('Credential-like filename in source inventory: '+name)
        if relative.parts[0] == 'historical' and relative.name not in {'INDEX.md', 'notes.md', 'README.md', 'source-preview.json'}:
            originals.append(name)
        if not selected(relative):
            continue
        path = root.joinpath(*relative.parts)
        if not path.is_file():
            continue  # Deleted tracked files are not part of a working-tree preview.
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Source link escapes or aliases the source inventory: '+name)
        files.append(path)
    ledger = root/'historical/source-preview.json'
    if ledger.is_file():
        prior = json.loads(ledger.read_text(encoding='utf-8'))
        if prior.get('format') != 1 or not isinstance(prior.get('omitted_originals'), list):
            raise ValueError('Invalid historical source-preview inventory')
        for name in prior['omitted_originals']:
            if not isinstance(name, str) or not name.startswith('historical/') or '..' in PurePosixPath(name).parts:
                raise ValueError('Invalid historical exclusion path')
            originals.append(name)
    return files, sorted(set(originals))


def check(root: Path) -> dict:
    root = root.resolve()
    for name in REQUIRED:
        if not (root/name).is_file():
            raise ValueError('Missing release file: '+name)
    files, originals = collect(root)
    for path in files:
        content = path.read_bytes()
        if SECRET.search(content):
            raise ValueError('Possible credential content in '+path.relative_to(root).as_posix())
        relative = path.relative_to(root).as_posix()
        if not relative.startswith('tests/fixtures/'):
            if path.suffix == '.json':
                json.loads(content.decode('utf-8-sig'))
            elif path.suffix == '.toml':
                tomllib.loads(content.decode('utf-8-sig'))
    for name in ('README.md', 'README.en.md', 'CONTRIBUTING.md', 'docs/building.md',
                 'docs/status.md', 'docs/release.md'):
        path = root/name
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if re.match(r'^[a-zA-Z][\w+.-]*:', link) or link.startswith('#'):
                continue
            target = link.split('#', 1)[0]
            if not (path.parent/target).exists():
                raise ValueError(f'Broken local link in {name}: {link}')
    return {'format': 1, 'release': VERSION, 'source_files': len(files),
            'historical_originals_excluded': originals, 'checks_passed': True}


def provenance(root: Path) -> dict:
    if not (root/'.git').exists():
        return {'git_commit': None, 'working_tree_dirty': None}
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = bool(subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain']))
    return {'git_commit': commit, 'working_tree_dirty': dirty}


def export_source(root: Path, output: Path) -> dict:
    root, output = root.resolve(), output.resolve()
    if output == root or root.is_relative_to(output):
        raise ValueError('Release output must not contain the source workspace')
    if output.is_relative_to(root) and output.relative_to(root).parts[0] != 'target':
        raise ValueError('In-workspace release output must be under target/')
    report = check(root)
    files, originals = collect(root)
    contents = {p.relative_to(root).as_posix(): p.read_bytes() for p in files}
    if originals:
        contents['historical/source-preview.json'] = (json.dumps({
            'format': 1, 'omitted_originals': originals,
            'reason': 'Historical original documents are managed separately from the source preview.'
        }, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    manifest = {'format': 1, 'release': VERSION, **provenance(root),
                'historical_originals_included': False, 'excluded_historical_files': originals,
                'files': {name: sha(data) for name, data in contents.items()}}
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    output.mkdir(parents=True, exist_ok=True)
    stem = 'naru-'+VERSION+'-source'
    archive = output/(stem+'.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name, data in sorted({**contents, 'naru-source-manifest.json': encoded}.items()):
            entry = zipfile.ZipInfo('naru-'+VERSION+'/'+name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(entry, data)
    (output/(stem+'.manifest.json')).write_bytes(encoded)
    digest = sha(archive.read_bytes())
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n', encoding='utf-8')
    return {**report, 'archive': str(archive), 'sha256': digest}


def check_package(package: Path) -> dict:
    package = package.resolve()
    metadata = json.loads((package/'naru-distribution.json').read_text(encoding='utf-8-sig'))
    for name in ('LICENSE', 'LICENSE-MIT', 'LICENSE-APACHE', 'NOTICE', 'THIRD_PARTY.md',
                 'README.md', 'naru.exe', 'naru_mlir_backend.dll',
                 'licenses/LLVM.txt', 'licenses/Vyx.txt', 'licenses/spdlog.txt', 'licenses/fmt.txt'):
        if not (package/name).is_file():
            raise ValueError('Missing distribution file: '+name)
    if metadata['c11']['full_conformance_claimed'] is not False:
        raise ValueError('Preview must retain the incomplete C11 status')
    for artifact in metadata['artifacts']:
        relative = PurePosixPath(artifact['file'].replace('\\', '/'))
        if relative.is_absolute() or '..' in relative.parts or ':' in relative.parts[0]:
            raise ValueError('Unsafe distribution artifact path')
        path = package.joinpath(*relative.parts)
        if not path.resolve().is_relative_to(package) or sha(path.read_bytes()) != artifact['sha256']:
            raise ValueError('Distribution artifact hash mismatch: '+relative.as_posix())
    lines = []
    for path in sorted(package.rglob('*')):
        if not path.is_file() or path.name == 'SHA256SUMS':
            continue
        relative = path.relative_to(package)
        if path.is_symlink() or not path.resolve().is_relative_to(package):
            raise ValueError('Linked file in distribution: '+relative.as_posix())
        if any(part in GENERATED for part in relative.parts) or PRIVATE_NAME.search(path.name):
            raise ValueError('Unexpected local/build file in distribution: '+relative.as_posix())
        data = path.read_bytes()
        if path.suffix not in {'.exe', '.dll', '.lib'} and SECRET.search(data):
            raise ValueError('Possible credential content in distribution: '+relative.as_posix())
        lines.append(sha(data)+'  '+relative.as_posix())
    (package/'SHA256SUMS').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return {'format': 1, 'package_files': len(lines), 'checks_passed': True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'source', 'check-package'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=ROOT/'target/release')
    parser.add_argument('--package', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'source':
            result = export_source(args.root, args.output)
        elif args.action == 'check-package':
            if not args.package:
                parser.error('check-package requires --package')
            result = check_package(args.package)
        else:
            result = check(args.root)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(f"PASS {args.action}: {result.get('source_files', result.get('package_files'))} files")
        if 'archive' in result:
            print(result['archive'])
        if result.get('historical_originals_excluded'):
            print(f"Historical originals excluded: {len(result['historical_originals_excluded'])}")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, 'Release preparation: '+str(error)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
