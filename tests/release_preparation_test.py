"""Source preview reproducibility, exclusion boundaries and SDK discovery."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


release = load('release_prepare', ROOT/'tools/release/prepare.py')
sdk = load('release_sdk', ROOT/'tools/vyx_sdk.py')


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)/'project'
        self.root.mkdir()
        for name in release.REQUIRED:
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('[package]\nversion="0.2.0"\n' if name.endswith('.toml') else 'Naru\n')

    def tearDown(self):
        self.temp.cleanup()

    def put(self, name, data=b'content'):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_archive_preserves_source_and_metadata_but_excludes_originals_and_builds(self):
        self.put('src/main.vyx')
        self.put('historical/c/11/INDEX.md')
        self.put('historical/c/11/notes.md')
        self.put('historical/c/11/original.pdf')
        self.put('historical/c/11/original.extract.md')
        self.put('examples/demo/target/demo.exe')
        self.put('packages/vyx-logger/vendor/local.cpp')
        self.put('web/src/App.vue')
        self.put('web/content/encyclopedia.mjs')
        output = self.root/'target/release'
        result = release.export_source(self.root, output)
        with zipfile.ZipFile(result['archive']) as package:
            names = package.namelist()
            self.assertTrue(any(n.endswith('/src/main.vyx') for n in names))
            self.assertTrue(any(n.endswith('/historical/c/11/INDEX.md') for n in names))
            self.assertFalse(any('original.' in n or '/vendor/' in n or n.endswith('.exe') for n in names))
            self.assertFalse(any('/web/' in n for n in names))
        self.assertIn('historical/c/11/original.pdf', result['historical_originals_excluded'])
        self.assertTrue((self.root/'historical/c/11/original.pdf').is_file())

    def test_same_snapshot_produces_identical_zip_bytes(self):
        self.put('src/main.vyx')
        first = release.export_source(self.root, self.root/'target/first')
        second = release.export_source(self.root, self.root/'target/second')
        self.assertEqual(Path(first['archive']).read_bytes(), Path(second['archive']).read_bytes())

    def test_clean_source_can_be_checked_and_reexported_without_originals_or_git(self):
        self.put('historical/c/11/INDEX.md')
        self.put('historical/c/11/original.pdf')
        first = release.export_source(self.root, self.root/'target/first')
        extracted = Path(self.temp.name)/'consumer'
        with zipfile.ZipFile(first['archive']) as package:
            package.extractall(extracted)
        clean = extracted/('naru-'+release.VERSION)
        self.assertTrue(release.check(clean)['checks_passed'])
        second = release.export_source(clean, clean/'target/second')
        self.assertEqual(first['historical_originals_excluded'], second['historical_originals_excluded'])
        self.assertEqual(Path(first['archive']).read_bytes(), Path(second['archive']).read_bytes())

    def test_output_cannot_pollute_source_or_contain_workspace(self):
        for output in (self.root, self.root.parent, self.root/'docs/release'):
            with self.assertRaises(ValueError):
                release.export_source(self.root, output)

    def test_secret_content_and_credential_names_fail_without_printing_contents(self):
        secret = b'-----BEGIN '+b'PRIVATE KEY-----\nnot-a-real-key'
        path = self.put('src/sample.c', secret)
        with self.assertRaisesRegex(ValueError, 'Possible credential content'):
            release.check(self.root)
        path.unlink()
        self.put('src/client.pem')
        with self.assertRaisesRegex(ValueError, 'Credential-like filename'):
            release.check(self.root)

    def test_missing_license_and_broken_entry_link_are_failures(self):
        (self.root/'README.md').write_text('[missing](docs/missing.md)')
        with self.assertRaisesRegex(ValueError, 'Broken local link'):
            release.check(self.root)
        (self.root/'LICENSE-MIT').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing release file'):
            release.check(self.root)

    def test_malformed_package_data_is_a_failure(self):
        self.put('registry/index.json', b'{invalid')
        with self.assertRaises(ValueError):
            release.check(self.root)

    def test_sdk_explicit_selection_wins_and_invalid_selection_does_not_fall_back(self):
        compiler = self.put('sdk/bin/vyxc.exe')
        with patch.dict(os.environ, {'VYX_SDK_ROOT': str(self.root/'missing')}, clear=True):
            self.assertEqual(sdk.resolve_sdk(compiler.parents[1]), compiler.parents[1])
            with self.assertRaises(ValueError):
                sdk.resolve_sdk(self.root/'missing')

    def test_sdk_local_install_and_missing_setup(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(sdk.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Vyx SDK not found'):
                sdk.resolve_sdk(root=self.root)
            compiler = self.put('.tools/vyx-sdk/bin/vyxc.exe')
            self.assertEqual(sdk.resolve_sdk(root=self.root), compiler.parents[1])

    def test_binary_manifest_cannot_escape_distribution(self):
        package = self.root/'target/package'
        package.mkdir(parents=True)
        required = ('LICENSE', 'LICENSE-MIT', 'LICENSE-APACHE', 'NOTICE', 'THIRD_PARTY.md',
                    'README.md', 'naru.exe', 'naru_mlir_backend.dll', 'licenses/LLVM.txt',
                    'licenses/Vyx.txt', 'licenses/spdlog.txt', 'licenses/fmt.txt')
        for name in required:
            path = package/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'test')
        (package/'naru-distribution.json').write_text(json.dumps({
            'c11': {'full_conformance_claimed': False},
            'artifacts': [{'file': '../outside', 'sha256': '0'*64}]}))
        with self.assertRaisesRegex(ValueError, 'Unsafe distribution artifact path'):
            release.check_package(package)

        metadata = {'c11': {'full_conformance_claimed': False},
                    'artifacts': [{'file': 'naru.exe', 'sha256': release.sha(b'test')}]}
        (package/'naru-distribution.json').write_text(json.dumps(metadata))
        self.assertTrue(release.check_package(package)['checks_passed'])
        self.assertIn('naru.exe', (package/'SHA256SUMS').read_text())
        (package/'naru.exe').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            release.check_package(package)


if __name__ == '__main__':
    unittest.main(verbosity=2)
