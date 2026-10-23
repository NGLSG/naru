"""Registry/Git transport acceptance tests, using isolated repositories and caches."""
from __future__ import annotations

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("naru_packages", ROOT / "tools/pkg/naru.py")
pkg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkg)
from native_process import execute


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_json(path, data):
    return put(path, pkg.json_text(data))


class Packages(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="naru packages 中文 ")
        self.root = Path(self.temporary.name)
        self.app = self.root / "app"
        put(self.app / "Naru.toml", '[package]\nname = "application"\nversion = "0.1.0"\n')
        self.cache = self.root / "cache"
        self.manager = pkg.Manager(self.app, cache=self.cache)

    def tearDown(self):
        self.temporary.cleanup()

    def library(self, name="language", release="1.0.0", module="language", directory=None, extra=""):
        path = directory or self.root / (name + "-" + release)
        put(path / "Naru.toml", f'[package]\nname = "{name}"\nversion = "{release}"\n'
            f'[exports]\n"{module}" = "rules/main.stx"\n' + extra)
        put(path / "rules/main.stx", f"mod {module}; effect answer() => 42;\n")
        return path

    def registry(self, packages, name="index.json"):
        releases = {}
        for package, versions in packages.items():
            releases[package] = {"description": "Test dialect", "versions": {
                release: {"source": source if isinstance(source, dict) else {"path": str(source)}}
                for release, source in versions.items()}}
        return write_json(self.root / name, {"format": 1, "packages": releases})

    def sources(self, dependencies, registry=None):
        return write_json(self.app / pkg.SOURCES, {"format": 1, "registries": {
            "default": str(registry or self.root / "index.json")}, "dependencies": dependencies})

    def git(self, directory, *arguments):
        result = subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def repository(self, directory):
        self.git(directory, "init", "--quiet")
        self.git(directory, "config", "user.name", "Naru acceptance")
        self.git(directory, "config", "user.email", "tests@example.invalid")
        return self.commit(directory)

    def commit(self, directory):
        self.git(directory, "add", ".")
        self.git(directory, "commit", "--quiet", "-m", "test release")
        return self.git(directory, "rev-parse", "HEAD")

    def simple(self):
        language = self.library()
        self.registry({"language": {"1.0.0": language}})
        self.sources({"lang": {"package": "language", "version": "^1.0.0"}})
        return language

    def test_template_and_real_compiler(self):
        project = self.root / "template"
        pkg.create_dialect(project, "template-language", "archive.language")
        manager = pkg.Manager(project, cache=self.cache)
        lock = manager.fetch()
        self.assertEqual(lock["packages"][0]["name"], "naru-stdlib")
        compiler = ROOT / "target/naru.exe"
        self.assertTrue(compiler.exists(), "build Naru before package acceptance tests")
        env = dict(os.environ, PATH="")
        for args in (["resolve", "--project", str(project)], ["build", "--project", str(project), "--locked"]):
            result = execute([str(compiler), *args], cwd=self.root, timeout=20,
                             env=env, memory_limit=512 * 1024 * 1024)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = execute([str(project / "target/template-language.exe")], cwd=self.root, timeout=3,
                         env=env, memory_limit=64 * 1024 * 1024)
        self.assertEqual(result.returncode, 42)

    def test_registry_selects_highest_compatible_version(self):
        self.registry({"language": {v: self.library(release=v) for v in ["1.2.0", "1.5.0", "2.0.0"]}})
        self.sources({"lang": {"package": "language", "version": "^1.2.0"}})
        lock = self.manager.fetch()
        self.assertEqual(lock["packages"][0]["version"], "1.5.0")
        text, data = pkg.manifest(self.app / "Naru.toml")
        self.assertEqual(data["dependencies"]["lang"]["path"], ".naru/packages/language")

    def test_registry_relative_path_source(self):
        library = self.library()
        self.registry({"language": {"1.0.0": {"path": library.name}}})
        self.sources({"lang": {"package": "language"}})
        self.assertEqual(self.manager.fetch()["packages"][0]["name"], "language")

    def test_git_commit_is_pinned_and_fetch_does_not_follow_head(self):
        repository = self.library()
        first = self.repository(repository)
        self.sources({"lang": {"git": str(repository), "package": "language", "rev": "HEAD"}})
        lock = self.manager.fetch()
        self.assertEqual(lock["packages"][0]["source"]["rev"], first)
        put(repository / "rules/main.stx", "mod language; effect answer() => 7;\n")
        second = self.commit(repository)
        unchanged = self.manager.fetch()
        self.assertEqual(unchanged, lock)
        updated = pkg.Manager(self.app, cache=self.cache).fetch(update=True)
        self.assertEqual(updated["packages"][0]["source"]["rev"], second)

    def test_git_tag(self):
        repository = self.library()
        commit = self.repository(repository)
        self.git(repository, "tag", "v1.0.0")
        self.sources({"lang": {"git": str(repository), "rev": "v1.0.0"}})
        self.assertEqual(self.manager.fetch()["packages"][0]["source"]["rev"], commit)

    def test_git_subdirectory_and_sibling_path_dependency(self):
        repository = self.root / "monorepo"
        leaf = self.library("leaf", module="leaf", directory=repository / "libraries/leaf")
        facade = self.library("facade", module="facade", directory=repository / "libraries/facade",
            extra='[dependencies]\nleaf = { path = "../leaf", package = "leaf", version = "^1.0.0" }\n')
        put(facade / "rules/main.stx", "mod facade; use leaf; effect answer() => leaf.answer();\n")
        commit = self.repository(repository)
        self.sources({"lang": {"git": str(repository), "subdir": "libraries/facade"}})
        lock = self.manager.fetch()
        self.assertEqual([p["name"] for p in lock["packages"]], ["facade", "leaf"])
        self.assertTrue(all(p["source"]["rev"] == commit for p in lock["packages"]))
        _, data = pkg.manifest(self.app / ".naru/packages/facade/Naru.toml")
        self.assertEqual(data["dependencies"]["leaf"]["path"], "../leaf")
        put(self.app / "Naru.toml", (self.app / "Naru.toml").read_text() + '[language]\ndialects = ["lang/facade"]\n')
        result = execute([str(ROOT / "target/naru.exe"), "resolve", "--project", str(self.app)],
                         cwd=self.root, timeout=20, env=dict(os.environ, PATH=""), memory_limit=512 * 1024 * 1024)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_registry_git_transport(self):
        repository = self.library()
        commit = self.repository(repository)
        self.registry({"language": {"1.0.0": {"git": str(repository), "rev": commit}}})
        self.sources({"lang": {"package": "language"}})
        self.assertEqual(self.manager.fetch()["packages"][0]["source"]["rev"], commit)

    def test_transitive_registry_dependency_and_diamond(self):
        leaf = self.library("leaf", module="leaf")
        middle = self.library("middle", module="middle")
        write_json(middle / pkg.SOURCES, {"format": 1, "dependencies": {"leaf": {"package": "leaf", "version": "^1.0.0"}}})
        self.registry({"leaf": {"1.0.0": leaf}, "middle": {"1.0.0": middle}})
        self.sources({"middle": {"package": "middle"}, "leaf": {"package": "leaf"}})
        lock = self.manager.fetch()
        self.assertEqual(len(lock["packages"]), 2)
        self.assertEqual(next(p for p in lock["packages"] if p["name"] == "middle")["dependencies"], {"leaf": "leaf"})

    def test_backtracking_finds_shared_compatible_version(self):
        leaf1 = self.library("leaf", "1.0.0", "leaf")
        leaf2 = self.library("leaf", "1.1.0", "leaf")
        middle = self.library("middle", module="middle")
        write_json(middle / pkg.SOURCES, {"format": 1, "dependencies": {"leaf": {"package": "leaf", "version": "1.0.0"}}})
        self.registry({"leaf": {"1.0.0": leaf1, "1.1.0": leaf2}, "middle": {"1.0.0": middle}})
        self.sources({"a_leaf": {"package": "leaf", "version": "^1.0.0"}, "z_middle": {"package": "middle"}})
        lock = self.manager.fetch()
        self.assertEqual(next(p for p in lock["packages"] if p["name"] == "leaf")["version"], "1.0.0")

    def test_conflicting_constraints_fail_without_writes(self):
        leaf1 = self.library("leaf", "1.0.0", "leaf")
        leaf2 = self.library("leaf", "2.0.0", "leaf")
        middle = self.library("middle", module="middle")
        write_json(middle / pkg.SOURCES, {"format": 1, "dependencies": {"leaf": {"package": "leaf", "version": "2.0.0"}}})
        self.registry({"leaf": {"1.0.0": leaf1, "2.0.0": leaf2}, "middle": {"1.0.0": middle}})
        self.sources({"leaf": {"package": "leaf", "version": "1.0.0"}, "middle": {"package": "middle"}})
        before = (self.app / "Naru.toml").read_bytes()
        with self.assertRaisesRegex(pkg.Error, "conflicting package identity"):
            self.manager.fetch()
        self.assertEqual((self.app / "Naru.toml").read_bytes(), before)
        self.assertFalse((self.app / pkg.LOCK).exists())

    def test_dependency_cycle(self):
        library = self.library()
        write_json(library / pkg.SOURCES, {"format": 1, "dependencies": {"self": {"package": "language"}}})
        self.registry({"language": {"1.0.0": library}})
        self.sources({"lang": {"package": "language"}})
        with self.assertRaisesRegex(pkg.Error, "dependency cycle"):
            self.manager.fetch()

    def test_missing_package_and_unsatisfied_version(self):
        self.simple()
        data = pkg.json_read(self.app / pkg.SOURCES)
        for spec, message in [({"package": "missing"}, "not found"), ({"package": "language", "version": "2.0.0"}, "no version")]:
            with self.subTest(spec=spec):
                data["dependencies"]["lang"] = spec
                with self.assertRaisesRegex(pkg.Error, message):
                    self.manager.fetch(replacement=data)

    def test_registry_manifest_version_and_name_must_match(self):
        library = self.library()
        self.registry({"language": {"2.0.0": library}})
        self.sources({"lang": {"package": "language"}})
        with self.assertRaisesRegex(pkg.Error, "registry version mismatch"):
            self.manager.fetch()
        self.registry({"other": {"1.0.0": library}})
        self.sources({"lang": {"package": "other"}})
        with self.assertRaisesRegex(pkg.Error, "name mismatch"):
            pkg.Manager(self.app, cache=self.cache).fetch()

    def test_offline_restore_from_cache(self):
        library = self.simple()
        lock = self.manager.fetch()
        shutil.rmtree(self.app / ".naru/packages")
        shutil.rmtree(library)
        shutil.rmtree(self.cache / "unused", ignore_errors=True)
        offline = pkg.Manager(self.app, cache=self.cache, offline=True)
        with patch.object(offline, "registry", side_effect=AssertionError("must not query registry")), patch.object(offline, "snapshot", side_effect=AssertionError("must not acquire")):
            self.assertEqual(offline.fetch(locked=True), lock)

    def test_locked_git_can_recover_cache_from_pinned_commit(self):
        repository = self.library()
        first = self.repository(repository)
        self.sources({"lang": {"git": str(repository)}})
        lock = self.manager.fetch()
        put(repository / "rules/main.stx", "mod language; effect answer() => 9;\n")
        self.commit(repository)
        shutil.rmtree(self.cache)
        shutil.rmtree(self.app / ".naru/packages")
        recovered = pkg.Manager(self.app, cache=self.cache).fetch(locked=True)
        self.assertEqual(recovered, lock)
        self.assertEqual(recovered["packages"][0]["source"]["rev"], first)

    def test_offline_missing_git_cache_fails(self):
        repository = self.library()
        self.repository(repository)
        self.sources({"lang": {"git": str(repository)}})
        self.manager.fetch()
        shutil.rmtree(self.cache)
        with self.assertRaisesRegex(pkg.Error, "offline mode"):
            pkg.Manager(self.app, cache=self.cache, offline=True).fetch(locked=True)

    def test_changed_local_source_cannot_replace_locked_content(self):
        library = self.simple()
        self.manager.fetch()
        put(library / "rules/main.stx", "mod language; effect answer() => 9;\n")
        shutil.rmtree(self.cache)
        with self.assertRaisesRegex(pkg.Error, "locked package content changed"):
            pkg.Manager(self.app, cache=self.cache).fetch(locked=True)

    def test_tampered_installed_package_and_cache_rejected(self):
        self.simple()
        lock = self.manager.fetch()
        installed = self.app / ".naru/packages/language/rules/main.stx"
        original = installed.read_bytes()
        installed.write_bytes(original + b"// edit")
        with self.assertRaisesRegex(pkg.Error, "installed package was modified"):
            self.manager.fetch(locked=True)
        installed.write_bytes(original)
        cached = self.cache / "objects" / lock["packages"][0]["source_sha256"] / "rules/main.stx"
        cached.write_text("bad", encoding="utf-8")
        with self.assertRaisesRegex(pkg.Error, "corrupt package cache"):
            self.manager.fetch(locked=True)

    def test_missing_and_stale_package_lock(self):
        self.simple()
        with self.assertRaisesRegex(pkg.Error, "missing or out of date"):
            self.manager.fetch(locked=True)
        self.manager.fetch()
        data = pkg.json_read(self.app / pkg.SOURCES)
        data["dependencies"]["lang"]["version"] = "1.0.0"
        with self.assertRaisesRegex(pkg.Error, "missing or out of date"):
            self.manager.fetch(locked=True, replacement=data)

    def test_registry_changes_require_explicit_update(self):
        self.simple()
        lock = self.manager.fetch()
        library = self.library(release="1.1.0")
        self.registry({"language": {"1.0.0": self.root / "language-1.0.0", "1.1.0": library}})
        self.assertEqual(pkg.Manager(self.app, cache=self.cache).fetch(), lock)
        self.assertEqual(pkg.Manager(self.app, cache=self.cache).fetch(update=True)["packages"][0]["version"], "1.1.0")

    def test_duplicate_registry_names_require_selection(self):
        library = self.library()
        one = self.registry({"language": {"1.0.0": library}})
        two = self.registry({"language": {"1.0.0": library}}, "another.json")
        data = {"format": 1, "registries": {"one": str(one), "two": str(two)}, "dependencies": {"lang": {"package": "language"}}}
        with self.assertRaisesRegex(pkg.Error, "multiple registries"):
            self.manager.fetch(replacement=data)
        data["dependencies"]["lang"]["registry"] = "two"
        self.assertEqual(len(self.manager.fetch(replacement=data)["packages"]), 1)

    def test_transaction_rolls_back_manifest_sources_lock_and_packages(self):
        library = self.simple()
        self.manager.fetch()
        before = {name: (self.app / name).read_bytes() for name in ["Naru.toml", pkg.SOURCES, pkg.LOCK]}
        before_files = pkg.files_at(self.app / ".naru/packages/language")
        put(library / "rules/main.stx", "mod language; effect answer() => 9;\n")
        real_atomic = pkg.atomic
        def fail_lock(path, text):
            if path == self.app / pkg.LOCK:
                raise OSError("injected disk failure")
            return real_atomic(path, text)
        with patch.object(pkg, "atomic", side_effect=fail_lock), self.assertRaisesRegex(OSError, "disk failure"):
            pkg.Manager(self.app, cache=self.cache).fetch(update=True)
        self.assertEqual(before, {name: (self.app / name).read_bytes() for name in before})
        self.assertEqual(before_files, pkg.files_at(self.app / ".naru/packages/language"))
        self.assertFalse((self.app / ".naru/pkg.guard").exists())

    def test_wrong_export_and_escaping_export_rejected(self):
        library = self.simple()
        put(library / "rules/main.stx", "mod wrong; effect answer() => 42;")
        with self.assertRaisesRegex(pkg.Error, "does not declare"):
            self.manager.fetch()
        put(library / "Naru.toml", '[package]\nname="language"\nversion="1.0.0"\n[exports]\nlanguage="../escape.stx"\n')
        with self.assertRaisesRegex(pkg.Error, "escapes"):
            pkg.Manager(self.app, cache=self.cache).fetch()

    def test_malicious_package_lock_paths(self):
        self.simple()
        lock = self.manager.fetch()
        lock["packages"][0]["files"]["../escape"] = "0" * 64
        with self.assertRaisesRegex(pkg.Error, "escapes"):
            self.manager.validate_lock(lock)
        lock["packages"][0]["files"].pop("../escape")
        lock["packages"][0]["name"] = "../escape"
        with self.assertRaisesRegex(pkg.Error, "invalid package name"):
            self.manager.validate_lock(lock)

    def test_managed_directory_refuses_unowned_contents(self):
        self.simple()
        put(self.app / ".naru/packages/personal.txt", "do not replace")
        with self.assertRaisesRegex(pkg.Error, "not managed"):
            self.manager.fetch()
        self.assertEqual((self.app / ".naru/packages/personal.txt").read_text(), "do not replace")

    def test_concurrent_guard(self):
        self.simple()
        with pkg.project_guard(self.app):
            with self.assertRaisesRegex(pkg.Error, "another package operation"):
                self.manager.fetch()

    def test_template_refuses_overwrite(self):
        with self.assertRaisesRegex(pkg.Error, "must be empty"):
            pkg.create_dialect(self.app, "language", "language")

    def test_git_template_keeps_builtin_dependency(self):
        repository = self.root / "template-repository"
        pkg.create_dialect(repository, "template-language", "template_language")
        self.repository(repository)
        self.sources({"lang": {"git": str(repository)}})
        lock = self.manager.fetch()
        self.assertEqual([p["name"] for p in lock["packages"]], ["naru-stdlib", "template-language"])

    def test_existing_local_dependency_is_shared_with_remote_library(self):
        leaf = self.library("leaf", module="leaf")
        middle = self.library("middle", module="middle")
        write_json(middle / pkg.SOURCES, {"format": 1, "dependencies": {"leaf": {"package": "leaf"}}})
        self.registry({"leaf": {"1.0.0": leaf}, "middle": {"1.0.0": middle}})
        self.sources({"middle": {"package": "middle"}})
        put(self.app / "Naru.toml", (self.app / "Naru.toml").read_text() +
            '[dependencies]\nlocal_leaf={path="../leaf-1.0.0",package="leaf",version="1.0.0"}\n')
        lock = self.manager.fetch()
        self.assertEqual(len(lock["packages"]), 2)
        self.assertEqual(lock["root_dependencies"]["local_leaf"], "leaf")
        self.assertEqual(pkg.json_read(self.app / pkg.SOURCES)["dependencies"]["local_leaf"]["path"], "../leaf-1.0.0")

    def test_embedded_git_registry_survives_temporary_export(self):
        repository = self.root / "monorepo"
        leaf = self.library("leaf", module="leaf", directory=repository / "leaf")
        middle = self.library("middle", module="middle", directory=repository / "middle")
        write_json(middle / "registry.json", {"format": 1, "packages": {"leaf": {
            "versions": {"1.0.0": {"source": {"path": "../leaf"}}}}}})
        write_json(middle / pkg.SOURCES, {"format": 1, "registries": {"embedded": "registry.json"},
            "dependencies": {"leaf": {"package": "leaf", "registry": "embedded"}}})
        self.repository(repository)
        self.sources({"middle": {"git": str(repository), "subdir": "middle"}})
        lock = self.manager.fetch()
        self.assertEqual([p["name"] for p in lock["packages"]], ["leaf", "middle"])

    def test_git_json_path_dependency_is_pinned_as_sibling(self):
        repository = self.root / "monorepo"
        self.library("leaf", module="leaf", directory=repository / "leaf")
        middle = self.library("middle", module="middle", directory=repository / "middle")
        write_json(middle / pkg.SOURCES, {"format": 1, "dependencies": {"leaf": {"path": "../leaf"}}})
        commit = self.repository(repository)
        self.sources({"middle": {"git": str(repository), "subdir": "middle"}})
        lock = self.manager.fetch()
        self.assertEqual(len(lock["packages"]), 2)
        self.assertTrue(all(p["source"]["rev"] == commit for p in lock["packages"]))

    def test_extra_installed_files_and_changed_marker_are_rejected(self):
        self.simple()
        self.manager.fetch()
        unexpected = put(self.app / ".naru/packages/keep.txt", "keep")
        with self.assertRaisesRegex(pkg.Error, "unmanaged file"):
            self.manager.fetch()
        unexpected.unlink()
        marker = self.app / ".naru/packages/.naru-managed.json"
        data = pkg.json_read(marker)
        data["packages"]["language"] = "0" * 64
        write_json(marker, data)
        with self.assertRaisesRegex(pkg.Error, "marker differs"):
            self.manager.fetch()

    def test_lock_cycle_is_rejected(self):
        self.simple()
        lock = self.manager.fetch()
        lock["packages"][0]["dependencies"]["self"] = "language"
        with self.assertRaisesRegex(pkg.Error, "cyclic"):
            self.manager.validate_lock(lock)

    def test_failed_update_preserves_previous_successful_graph(self):
        self.simple()
        self.manager.fetch()
        before = {name: (self.app / name).read_bytes() for name in ["Naru.toml", pkg.SOURCES, pkg.LOCK]}
        (self.root / "index.json").unlink()
        with self.assertRaises(pkg.Error):
            self.manager.fetch(update=True)
        self.assertEqual(before, {name: (self.app / name).read_bytes() for name in before})

    def test_case_colliding_package_identities_are_rejected(self):
        lower = self.library("language", module="language")
        upper = self.library("Language", module="Language")
        self.registry({"language": {"1.0.0": lower}, "Language": {"1.0.0": upper}})
        self.sources({"one": {"package": "language"}, "two": {"package": "Language"}})
        with self.assertRaisesRegex(pkg.Error, "case-colliding"):
            self.manager.fetch()

    def test_package_scripts_and_git_hooks_are_not_executed(self):
        repository = self.library()
        put(repository / "install.ps1", "throw 'must not execute'\n")
        self.repository(repository)
        self.sources({"lang": {"git": str(repository)}})
        self.assertEqual(len(self.manager.fetch()["packages"]), 1)

    def test_scp_style_ssh_repository(self):
        self.assertEqual(pkg.source_spec({"git": "git@example.invalid:team/language.git"}, self.root)["git"],
                         "git@example.invalid:team/language.git")

    def test_cli_wrapper_build_fetches_and_passes_original_compiler_options(self):
        project = self.root / "wrapper"
        pkg.create_dialect(project, "wrapper-language", "wrapper_language")
        with patch.object(pkg.subprocess, "call", return_value=0) as call:
            code = pkg.main(["build", "--project", str(project), "--target", "mlir"])
        self.assertEqual(code, 0)
        self.assertTrue((project / pkg.LOCK).exists())
        self.assertEqual(call.call_args.args[0][1:], ["build", "--project", str(project), "--target", "mlir"])

    def test_relocated_local_registry_can_restore_identical_locked_content(self):
        old = self.simple()
        lock = self.manager.fetch()
        relocated = self.root / "relocated-language"
        shutil.copytree(old, relocated)
        shutil.rmtree(old)
        self.registry({"language": {"1.0.0": relocated}})
        shutil.rmtree(self.cache)
        shutil.rmtree(self.app / ".naru/packages")
        self.assertEqual(pkg.Manager(self.app, cache=self.cache, offline=True).fetch(locked=True), lock)

    def test_bundled_sdk_can_relocate_without_changing_locked_content(self):
        project = self.root / "template"
        pkg.create_dialect(project, "template-language", "template_language")
        lock = pkg.Manager(project, cache=self.cache).fetch()
        # Simulate a lock generated at another SDK path; content identity stays
        # locked and recovery uses the current SDK's local registry.
        lock["packages"][0]["source"]["path"] = str(self.root / "old-sdk/dialects")
        write_json(project / pkg.LOCK, lock)
        shutil.rmtree(self.cache)
        shutil.rmtree(project / ".naru/packages")
        restored = pkg.Manager(project, cache=self.cache, offline=True).fetch(locked=True)
        self.assertEqual(restored, lock)

    def test_registry_git_package_builds_with_transitive_base(self):
        repository = self.root / "remote-rules"
        pkg.create_dialect(repository, "remote-rules", "remote_rules")
        self.repository(repository)
        index = self.registry({"remote-rules": {"0.1.0": {"git": str(repository)}}})
        self.sources({"history": {"package": "remote-rules"}}, index)
        put(self.app / "main.nru", "fn main() -> i32 { return answer; }\n")
        put(self.app / "Naru.toml", '[package]\nname="application"\nversion="0.1.0"\nentry="main.nru"\n'
            '[language]\ndialects=["history/remote_rules"]\nrelation="base.emit_program"\nunit="program"\n'
            '[backend]\ntarget="exe"\n')
        self.manager.fetch()
        env = dict(os.environ, PATH="")
        result = execute([str(ROOT / "target/naru.exe"), "build", "--project", str(self.app)],
                         cwd=self.root, timeout=20, env=env, memory_limit=512 * 1024 * 1024)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = execute([str(self.app / "target/application.exe")], cwd=self.root,
                         timeout=3, env=env, memory_limit=64 * 1024 * 1024)
        self.assertEqual(result.returncode, 42)

    def test_wrapper_protects_package_metadata_and_hardlink_alias(self):
        self.simple()
        self.manager.fetch()
        metadata = self.app / pkg.SOURCES
        alias = self.root / "metadata-alias.json"
        os.link(metadata, alias)
        for path in [metadata, self.app / pkg.LOCK, alias, self.app / ".naru/packages/language/new.mlir"]:
            with self.subTest(path=path):
                before = metadata.read_bytes()
                with patch.object(pkg.subprocess, "call", side_effect=AssertionError("must not invoke compiler")):
                    self.assertEqual(pkg.main(["build", "--project", str(self.app), "-o", str(path)]), 1)
                self.assertEqual(metadata.read_bytes(), before)

    def test_wrapper_protects_manifest_default_output(self):
        self.simple()
        put(self.app / "Naru.toml", (self.app / "Naru.toml").read_text() + '[build]\noutput="Naru.packages.json"\n')
        before = (self.app / pkg.SOURCES).read_bytes()
        with patch.object(pkg.subprocess, "call", side_effect=AssertionError("must not invoke compiler")):
            self.assertEqual(pkg.main(["build", "--project", str(self.app)]), 1)
        self.assertEqual((self.app / pkg.SOURCES).read_bytes(), before)

    def test_json_duplicate_keys_and_unknown_fields(self):
        put(self.app / pkg.SOURCES, '{"format":1,"format":1,"dependencies":{}}')
        with self.assertRaisesRegex(pkg.Error, "duplicate JSON key"):
            self.manager.fetch()
        write_json(self.app / pkg.SOURCES, {"format": 1, "dependencies": {}, "unknown": True})
        with self.assertRaisesRegex(pkg.Error, "unsupported package source"):
            self.manager.fetch()

    def test_version_rules_match_native_subset(self):
        for actual, requirement, expected in [
            ("1.9.2", "^1.2.3", True), ("2.0.0", "^1.2.3", False),
            ("0.2.9", "^0.2.3", True), ("0.3.0", "^0.2.3", False),
            ("0.0.4", "^0.0.3", False), ("0.0.3", "^0.0.3", True),
            ("1.2.9", "~1.2.3", True), ("1.3.0", "~1.2.3", False),
            ("1.2.2", "~1.2.3", False), ("5.0.0", "*", True)]:
            self.assertEqual(pkg.matches(actual, requirement), expected, (actual, requirement))
        for invalid in ["01.2.3", ">=1.0.0", "1.0.0-alpha"]:
            with self.assertRaises(pkg.Error):
                pkg.matches("1.0.0", invalid)

    def test_sources_validate_before_fetch(self):
        for dependency in [{"package": "../escape"}, {"package": "language", "unexpected": "x"},
                           {"package": "language", "git": "x", "registry": "default"}]:
            self.sources({"lang": dependency})
            with self.assertRaises(pkg.Error):
                self.manager.fetch()

    def test_git_source_validation(self):
        for source in [{"git": "ext::evil"}, {"git": "-option"}, {"git": "x", "rev": "-bad"},
                       {"git": "x", "subdir": "../escape"}, {"git": "x", "path": "y"}]:
            with self.assertRaises(pkg.Error):
                pkg.source_spec(source, self.root)

    def test_http_registry_and_offline_policy(self):
        self.registry({})
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(self.root)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/index.json"
            self.assertEqual(self.manager.registry(url)[0]["packages"], {})
            with self.assertRaisesRegex(pkg.Error, "offline"):
                pkg.Manager(self.app, offline=True).registry(url)
            with self.assertRaisesRegex(pkg.Error, "HTTPS"):
                self.manager.registry("http://example.invalid/index.json")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_native_dependency_path_tampering_is_rejected(self):
        self.simple()
        self.manager.fetch()
        path = self.app / "Naru.toml"
        path.write_text(path.read_text().replace('.naru/packages/language', 'elsewhere'), encoding="utf-8")
        with self.assertRaisesRegex(pkg.Error, "managed compiler dependency changed"):
            self.manager.fetch(locked=True)

    def test_cli_add_selects_dialect_without_losing_language_settings(self):
        library = self.library()
        registry = self.registry({"language": {"1.0.0": library}})
        self.sources({})
        put(self.app / "Naru.toml", (self.app / "Naru.toml").read_text() + '[language]\nentry="item"\ndialects=[\n]\nrelation="language.answer"\n')
        code = pkg.main(["pkg", "add", "language@^1.0.0", "--name", "lang", "--dialect", "language",
                         "--project", str(self.app), "--cache", str(self.cache)])
        self.assertEqual(code, 0)
        _, data = pkg.manifest(self.app / "Naru.toml")
        self.assertEqual(data["language"]["dialects"], ["lang/language"])
        self.assertEqual(data["language"]["relation"], "language.answer")

    def test_cli_bad_dialect_does_not_partially_install(self):
        self.simple()
        self.sources({})
        original = (self.app / "Naru.toml").read_bytes()
        code = pkg.main(["pkg", "add", "language", "--dialect", "missing", "--project", str(self.app)])
        self.assertEqual(code, 1)
        self.assertEqual((self.app / "Naru.toml").read_bytes(), original)
        self.assertFalse((self.app / pkg.LOCK).exists())

    def test_cli_git_add_and_alias(self):
        repository = self.library()
        self.repository(repository)
        self.sources({})
        code = pkg.main(["pkg", "add", str(repository), "--git", "--name", "lang", "--project", str(self.app)])
        self.assertEqual(code, 0)
        self.assertEqual(pkg.json_read(self.app / pkg.LOCK)["root_dependencies"], {"lang": "language"})


if __name__ == "__main__":
    started = time.perf_counter()
    program = unittest.main(verbosity=2, exit=False)
    result = program.result
    sources = [ROOT / "tools/pkg/naru.py", ROOT / "naru.ps1", Path(__file__).resolve(),
               *(ROOT / "registry").rglob("*.json"), *(ROOT / "templates/dialect").rglob("*")]
    write_json(ROOT / "target/packages-report.json", {
        "format": 1, "passed": result.wasSuccessful(), "checks": result.testsRun,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "failures": [str(test) for test, _ in [*result.failures, *result.errors]],
        "source_sha256": {path.relative_to(ROOT).as_posix(): pkg.file_digest(path) for path in sources if path.is_file()},
        "compiler_sha256": pkg.file_digest(ROOT / "target/naru.exe")
    })
    raise SystemExit(0 if result.wasSuccessful() else 1)
