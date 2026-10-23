"""Naru package transport and CLI. The compiler still loads ordinary path packages.

Requires Python 3.11+. Git is used only to acquire Git sources; package scripts,
hooks, native builds, and compiler bootstraps are never run by this tool.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen
import uuid

ROOT = Path(__file__).resolve().parents[2]
SOURCES = "Naru.packages.json"
LOCK = "Naru.packages.lock"
MAX_FILES = 20000
MAX_BYTES = 256 * 1024 * 1024
IGNORED = {".git", ".naru", ".cache", "target", "node_modules", "__pycache__"}
NAME = re.compile(r"[a-zA-Z_][a-zA-Z0-9_-]*\Z")
MODULE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*\Z")


class Error(Exception):
    pass


class Conflict(Error):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Error(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def json_read(path):
    try:
        if path.stat().st_size > 4 * 1024 * 1024:
            raise Error(f"JSON input exceeds 4 MiB: {path}")
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs)
    except (OSError, ValueError) as exc:
        raise Error(f"cannot read JSON {path}: {exc}") from exc


def atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def linked(path):
    try:
        attributes = path.lstat()
    except FileNotFoundError:
        return False
    # is_junction is only in Python 3.12+. The Windows reparse attribute also
    # protects junctions when using the supported Python 3.11 runtime.
    return stat.S_ISLNK(attributes.st_mode) or bool(getattr(attributes, "st_file_attributes", 0) & 0x400)


def safe_name(name):
    if not isinstance(name, str) or not NAME.fullmatch(name) or name.upper() in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))
    }:
        raise Error(f"invalid package name or dependency alias: {name!r}")
    return name


def version(text):
    if not isinstance(text, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", text):
        raise Error(f"version must be stable major.minor.patch: {text!r}")
    result = tuple(map(int, text.split(".")))
    if any(part > 999999 for part in result):
        raise Error(f"version component exceeds compiler limit: {text}")
    return result


def matches(actual, requested):
    current = version(actual)
    if requested == "*":
        return True
    if not isinstance(requested, str):
        raise Error("version constraint must be text")
    prefix = requested[:1] if requested[:1] in {"^", "~"} else ""
    lower = version(requested[1:] if prefix else requested)
    if not prefix:
        return current == lower
    if current < lower:
        return False
    if prefix == "~" or lower[0] == 0 and lower[1] != 0:
        return current[:2] == lower[:2]
    if lower[:2] == (0, 0):
        return current == lower
    return current[0] == lower[0]


def relative_path(text):
    if not isinstance(text, str) or not text or "\\" in text or "\x00" in text:
        raise Error(f"invalid package relative path: {text!r}")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"..", "."} or any(c in part for c in ':<>"|?*') for part in path.parts):
        raise Error(f"package path escapes its root: {text}")
    for part in path.parts:
        if part.endswith((".", " ")) or part.split(".")[0].upper() in {
            "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))
        }:
            raise Error(f"nonportable package path: {text}")
    return path


def contained(path, base):
    if not path.resolve().is_relative_to(base.resolve()) or path.resolve() == base.resolve():
        raise Error(f"managed path escapes its directory: {path}")
    for parent in (path, *path.parents):
        if parent == base.parent:
            break
        if linked(parent):
            raise Error(f"managed path contains a link or junction: {parent}")


def remove_tree(path, base):
    contained(path, base)
    if path.exists():
        shutil.rmtree(path)


def files_at(directory):
    if not directory.is_dir() or linked(directory):
        raise Error(f"package directory is missing or linked: {directory}")
    files = {}
    total = 0
    folded = set()
    for parent, directories, names in os.walk(directory, followlinks=False):
        for name in (*directories, *names):
            path = Path(parent) / name
            if linked(path):
                raise Error(f"package links are unsupported: {path}")
        directories[:] = sorted(name for name in directories if name not in IGNORED)
        for name in sorted(names):
            if name in {LOCK, "Naru.lock"} or name.endswith(".pyc"):
                continue
            path = Path(parent) / name
            rel = path.relative_to(directory).as_posix()
            relative_path(rel)
            if rel.casefold() in folded:
                raise Error(f"case-colliding package path: {rel}")
            folded.add(rel.casefold())
            total += path.stat().st_size
            if len(files) >= MAX_FILES or total > MAX_BYTES:
                raise Error("package exceeds 20,000 files or 256 MiB")
            files[rel] = file_digest(path)
    return files


def copy_files(source, destination, files):
    destination.mkdir(parents=True, exist_ok=True)
    for name in files:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)


def manifest(path):
    try:
        text = path.read_text(encoding="utf-8-sig")
        data = tomllib.loads(text)
    except (OSError, ValueError) as exc:
        raise Error(f"invalid Naru manifest {path}: {exc}") from exc
    package = data.get("package", {})
    if not isinstance(package, dict) or not isinstance(data.get("exports", {}), dict):
        raise Error("package and exports must be tables")
    safe_name(package.get("name"))
    version(package.get("version"))
    for name, export in data.get("exports", {}).items():
        if not MODULE.fullmatch(name):
            raise Error(f"invalid dialect export: {name}")
        relative_path(export)
        exported = path.parent / export
        if not exported.is_file() or not exported.resolve().is_relative_to(path.parent.resolve()):
            raise Error(f"missing or escaping dialect export: {name} = {export}")
        # Linking ultimately verifies identities and imports; catch wrong exports
        # before installing a package, without treating a comment as a declaration.
        source = exported.read_text(encoding="utf-8-sig")
        source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
        declaration = re.match(r"\s*mod\s+([A-Za-z_][\w.]*)\s*;", source)
        if not declaration or declaration[1] != name:
            raise Error(f"dialect export {name} does not declare that module: {export}")
    dependencies = data.get("dependencies", {})
    if not isinstance(dependencies, dict):
        raise Error("dependencies must be a table")
    for alias, dependency in dependencies.items():
        safe_name(alias)
        if not isinstance(dependency, dict) or not isinstance(dependency.get("path"), str):
            raise Error(f"compiler dependency requires a path: {alias}")
    return text, data


def rewrite_dependencies(text, dependencies):
    # Preserve all other sections verbatim. The compiler's TOML subset does not
    # have multiline strings, so section boundaries can be located linewise.
    output = []
    discard = False
    for line in text.splitlines(keepends=True):
        header = re.fullmatch(r"\s*\[([^\]]+)\]\s*(?:#[^\n]*)?\r?\n?", line)
        if header:
            table = tomllib.loads("[" + header[1] + "]\n")
            discard = "dependencies" in table
        if not discard:
            output.append(line)
    result = "".join(output).rstrip() + "\n"
    if dependencies:
        result += "\n[dependencies]\n"
        for alias, fields in sorted(dependencies.items()):
            safe_name(alias)
            members = ", ".join(f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in sorted(fields.items()))
            result += f"{alias} = {{ {members} }}\n"
    return result


def select_dialects(text, root_data, alias, modules):
    language = dict(root_data.get("language", {}))
    references = list(language.get("dialects", []))
    references.extend(f"{alias}/{name}" for name in modules if f"{alias}/{name}" not in references)
    language["dialects"] = references
    lines = []
    discard = False
    for line in text.splitlines(keepends=True):
        header = re.fullmatch(r"\s*\[([^\]]+)\]\s*(?:#[^\n]*)?\r?\n?", line)
        if header:
            discard = "language" in tomllib.loads("[" + header[1] + "]\n")
        if not discard:
            lines.append(line)
    return "".join(lines).rstrip() + "\n\n[language]\n" + "".join(
        key + " = " + json.dumps(value, ensure_ascii=False) + "\n" for key, value in language.items())


def normalize_location(value, base):
    if value == "builtin":
        return str(ROOT / "registry/index.json")
    if not isinstance(value, str) or not value or "\x00" in value:
        raise Error("registry location must be nonempty text")
    parsed = urlparse(value)
    if parsed.scheme in {"https", "http"}:
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise Error("remote registries require HTTPS")
        return value
    if isinstance(base, str) and urlparse(base).scheme in {"http", "https"}:
        return normalize_location(urljoin(base, value), Path.cwd())
    return str((Path(base) / value).resolve())


def source_spec(value, base):
    if not isinstance(value, dict) or set(value) - {"path", "git", "rev", "subdir"}:
        raise Error("source accepts path OR git, rev and optional subdir")
    if ("path" in value) == ("git" in value):
        raise Error("source requires exactly one of path or git")
    if "path" in value:
        if set(value) != {"path"} or isinstance(base, str) and urlparse(base).scheme in {"http", "https"}:
            raise Error("path sources require a local registry")
        if not isinstance(value["path"], str) or not value["path"] or "\x00" in value["path"]:
            raise Error("path source must be nonempty text")
        return {"path": str((Path(base) / value["path"]).resolve())}
    repo = value["git"]
    if not isinstance(repo, str) or not repo or repo.startswith("-") or "\x00" in repo:
        raise Error("invalid Git repository location")
    parsed = urlparse(repo)
    scp = re.fullmatch(r"[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+:[A-Za-z0-9_./-]+", repo)
    if parsed.scheme not in {"https", "ssh"} and not scp:
        if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            pass
        elif parsed.scheme and not re.match(r"^[A-Za-z]:[\\/]", repo):
            raise Error("Git sources accept HTTPS, SSH or a local repository path")
        elif isinstance(base, str) and urlparse(base).scheme in {"http", "https"}:
            raise Error("remote registry Git sources require an absolute HTTPS/SSH URL")
        else:
            repo = str((Path(base) / repo).resolve())
    rev = value.get("rev", "HEAD")
    if not isinstance(rev, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]*", rev) or ".." in rev:
        raise Error(f"invalid Git revision: {rev!r}")
    subdir = value.get("subdir", "")
    if not isinstance(subdir, str):
        raise Error("Git package subdir must be text")
    if subdir:
        relative_path(subdir)
    return {"git": repo, "rev": rev, "subdir": subdir}


def config(path, inherited=None):
    if path.is_file():
        data = json_read(path)
    else:
        data = {"format": 1, "dependencies": {}}
    if not isinstance(data, dict) or type(data.get("format")) is not int or data.get("format") != 1 or set(data) - {"format", "registries", "dependencies"}:
        raise Error(f"unsupported package source configuration: {path}")
    registries = dict(inherited) if inherited is not None else {"default": "builtin"}
    declared = data.get("registries", {})
    dependencies = data.get("dependencies", {})
    if not isinstance(declared, dict) or not isinstance(dependencies, dict):
        raise Error("registries and dependencies must be objects")
    for alias, location in declared.items():
        safe_name(alias)
        registries[alias] = normalize_location(location, path.parent)
    for alias, dependency in dependencies.items():
        safe_name(alias)
        validate_request(dependency)
    data.setdefault("dependencies", {})
    return data, registries


def validate_request(spec):
    if not isinstance(spec, dict) or set(spec) - {"package", "version", "registry", "git", "rev", "subdir", "path"}:
        raise Error("unknown package dependency field")
    if "package" in spec:
        safe_name(spec["package"])
    matches("0.0.0", spec.get("version", "*"))
    if "git" in spec or "path" in spec:
        if "registry" in spec:
            raise Error("a dependency cannot combine registry and Git/path sources")
    elif "package" not in spec:
        raise Error("registry dependency requires package")
    elif "rev" in spec or "subdir" in spec:
        raise Error("registry dependencies cannot override revision or subdir")
    if "registry" in spec:
        safe_name(spec["registry"])


def project_directory(value=None):
    if value:
        path = Path(value).resolve()
        return path.parent if path.name == "Naru.toml" else path
    for path in (Path.cwd(), *Path.cwd().parents):
        if (path / "Naru.toml").is_file():
            return path
    raise Error("no Naru.toml found; specify --project")


@contextmanager
def project_guard(project):
    managed = project / ".naru"
    contained(managed, project)
    managed.mkdir(exist_ok=True)
    guard = managed / "pkg.guard"
    try:
        descriptor = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise Error(f"another package operation is active ({guard}); remove a stale guard after checking its PID") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        yield
    finally:
        guard.unlink(missing_ok=True)


class Manager:
    def __init__(self, project, *, cache=None, offline=False):
        self.project = project.resolve()
        self.offline = offline
        self.cache = Path(cache or os.environ.get("NARU_PACKAGE_CACHE", self.project / ".naru/cache")).resolve()
        self.registry_cache = {}
        self.snapshots = {}
        self.choices = 0
        self.active_registries = {"default": "builtin"}

    def registry(self, location):
        location = normalize_location(location, self.project)
        if location in self.registry_cache:
            return self.registry_cache[location]
        if urlparse(location).scheme in {"http", "https"}:
            if self.offline:
                raise Error("offline mode cannot query a remote registry; use a package lock")
            try:
                with urlopen(location, timeout=15) as response:
                    raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise Error("registry exceeds 4 MiB")
                data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_pairs)
            except (OSError, ValueError) as exc:
                raise Error(f"cannot load registry {location}: {exc}") from exc
            base = location
        else:
            data = json_read(Path(location))
            base = Path(location).parent
        if not isinstance(data, dict) or type(data.get("format")) is not int or data.get("format") != 1 or set(data) - {"format", "packages"} or not isinstance(data.get("packages"), dict):
            raise Error("registry requires format 1 and a packages object")
        if len({name.casefold() for name in data["packages"]}) != len(data["packages"]):
            raise Error("case-colliding registry package identities")
        for name, package in data["packages"].items():
            safe_name(name)
            if not isinstance(package, dict) or set(package) - {"description", "homepage", "versions"} or not isinstance(package.get("versions"), dict):
                raise Error(f"invalid registry entry: {name}")
            if any(not isinstance(package.get(field, ""), str) for field in ("description", "homepage")):
                raise Error(f"registry description and homepage must be text: {name}")
            for release, entry in package["versions"].items():
                version(release)
                if not isinstance(entry, dict) or set(entry) != {"source"}:
                    raise Error(f"registry release requires source: {name}@{release}")
                source_spec(entry["source"], base)
        self.registry_cache[location] = (data, base)
        return data, base

    def git(self, directory, *arguments):
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1")
        for key in list(env):
            if key.startswith("GIT_") and key not in {"GIT_TERMINAL_PROMPT", "GIT_CONFIG_NOSYSTEM"}:
                del env[key]
        command = ["git", "-c", "core.hooksPath=" + str(directory / ".disabled-hooks"),
                   "-c", "core.fsmonitor=false", "-c", "protocol.ext.allow=never",
                   "-c", "protocol.file.allow=always", "-C", str(directory), *arguments]
        try:
            result = subprocess.run(command, capture_output=True, env=env, timeout=90)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise Error(f"Git acquisition failed: {exc}") from exc
        if result.returncode:
            raise Error("Git acquisition failed: " + result.stderr.decode("utf-8", errors="replace").strip())
        return result.stdout

    def snapshot(self, source):
        key = digest(source)
        if key in self.snapshots:
            return self.snapshots[key]
        self.cache.mkdir(parents=True, exist_ok=True)
        if "path" in source:
            directory = Path(source["path"])
            repo_root = directory
            resolved = source
        else:
            if self.offline:
                raise Error("offline mode needs an existing package lock and cached packages")
            with tempfile.TemporaryDirectory(prefix="naru-git-") as temporary:
                work = Path(temporary)
                self.git(work, "init", "--quiet")
                self.git(work, "fetch", "--quiet", "--depth=1", "--no-tags", "--", source["git"], source["rev"])
                commit = self.git(work, "rev-parse", "FETCH_HEAD^{commit}").decode().strip()
                if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
                    raise Error("Git did not return a commit identity")
                archive = work / "source.tar"
                self.git(work, "archive", "--format=tar", "--output=" + str(archive), commit)
                if archive.stat().st_size > MAX_BYTES + MAX_FILES * 1024:
                    raise Error("Git source exceeds acquisition size limit")
                repo_root = work / "export"
                repo_root.mkdir()
                total = 0
                seen = set()
                with tarfile.open(archive) as stream:
                    for item in stream:
                        relative = relative_path(item.name.rstrip("/"))
                        folded = str(relative).casefold()
                        if folded in seen or len(seen) >= MAX_FILES:
                            raise Error("duplicate/case-colliding or excessive Git archive paths")
                        seen.add(folded)
                        if item.isdir():
                            continue
                        if not item.isfile():
                            raise Error("Git archive links and special files are unsupported")
                        total += item.size
                        if total > MAX_BYTES:
                            raise Error("Git source exceeds 256 MiB")
                        target = repo_root / str(relative)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with stream.extractfile(item) as incoming, target.open("wb") as outgoing:
                            shutil.copyfileobj(incoming, outgoing)
                directory = repo_root / source.get("subdir", "")
                resolved = {**source, "rev": commit}
                result = self.save_snapshot(directory, resolved, repo_root)
                self.snapshots[key] = result
                return result
        result = self.save_snapshot(directory, resolved, repo_root)
        self.snapshots[key] = result
        return result

    def save_snapshot(self, directory, source, repo_root):
        text, data = manifest(directory / "Naru.toml")
        files = files_at(directory)
        tree = digest(files)
        destination = self.cache / "objects" / tree
        if destination.exists():
            if files_at(destination) != files:
                raise Error(f"corrupt package cache: {destination}")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = destination.parent / (".stage-" + uuid.uuid4().hex)
            try:
                copy_files(directory, staging, files)
                if files_at(staging) != files:
                    raise Error("package source changed during acquisition")
                try:
                    staging.rename(destination)
                except FileExistsError:
                    if files_at(destination) != files:
                        raise Error("concurrent package cache write differs")
            finally:
                remove_tree(staging, self.cache)
        # Resolve local dependencies against the original repository, before its
        # temporary export disappears. A sibling inside a Git repo shares its pin.
        local_sources = {}
        for alias, entry in data.get("dependencies", {}).items():
            child = (directory / entry["path"]).resolve()
            if "git" in source:
                if not child.is_relative_to(repo_root.resolve()):
                    raise Error(f"Git package path dependency escapes repository: {alias}")
                local_sources[alias] = {**source, "subdir": child.relative_to(repo_root).as_posix()}
            else:
                local_sources[alias] = {"path": str(child)}
        result = {"name": data["package"]["name"], "version": data["package"]["version"],
                  "source": source, "source_sha256": tree, "files": files, "dependencies": {},
                  "_directory": destination, "_data": data, "_local": local_sources}
        child_config, declared_indexes = config(directory / SOURCES, {})
        result["_requests"] = child_config["dependencies"]
        result["_registries"] = declared_indexes
        if "git" in source:
            for location in declared_indexes.values():
                if urlparse(location).scheme in {"http", "https"} or location in {"builtin", str(ROOT / "registry/index.json")}:
                    continue
                index, index_base = self.registry(location)
                # A registry bundled in the source export must remain usable
                # after the export is removed. Resolve repository-local paths
                # into sibling packages at this same pinned commit.
                rewritten = json.loads(json_text(index))
                for entry in rewritten["packages"].values():
                    for release in entry["versions"].values():
                        transport = source_spec(release["source"], index_base)
                        if "path" in transport:
                            child = Path(transport["path"])
                            if not child.is_relative_to(repo_root.resolve()):
                                raise Error("embedded Git registry path source escapes its repository")
                            transport = {**source, "subdir": child.relative_to(repo_root).as_posix()}
                        release["source"] = transport
                self.registry_cache[normalize_location(location, self.project)] = (rewritten, index_base)
        # Requests using local paths in a Git source must point into that repo;
        # turn them into sibling packages at the same immutable commit.
        for alias, request in list(result["_requests"].items()):
            if "path" in request:
                child = (directory / request["path"]).resolve()
                if "git" in source:
                    if not child.is_relative_to(repo_root.resolve()):
                        raise Error(f"Git package JSON path dependency escapes repository: {alias}")
                    transport = {**source, "subdir": child.relative_to(repo_root).as_posix()}
                else:
                    transport = {"path": str(child)}
                result["_requests"][alias] = {**request, **transport}
                if "git" in source:
                    del result["_requests"][alias]["path"]
        return result

    def candidates(self, request, registries, base):
        wanted = request.get("version", "*")
        if "git" in request or "path" in request:
            raw = {k: v for k, v in request.items() if k in {"git", "path", "rev", "subdir"}}
            return [(None, source_spec(raw, base))]
        name = request["package"]
        selected = [request["registry"]] if "registry" in request else sorted(registries)
        available = []
        for alias in selected:
            if alias not in registries:
                raise Error(f"unknown registry: {alias}")
            index, registry_base = self.registry(registries[alias])
            if name in index["packages"]:
                available.append((alias, index["packages"][name], registry_base))
        if len(available) > 1:
            raise Error(f"package {name} occurs in multiple registries; specify registry")
        if not available:
            raise Conflict(f"package not found in selected registries: {name}")
        alias, entry, registry_base = available[0]
        releases = sorted((v for v in entry["versions"] if matches(v, wanted)), key=version, reverse=True)
        if not releases:
            raise Conflict(f"no version of {name} satisfies {wanted}")
        return [(release, source_spec(entry["versions"][release]["source"], registry_base)) for release in releases]

    def resolve(self, data, registries, root_data):
        self.choices = 0
        root_name = root_data["package"]["name"]
        pending = [(None, alias, spec, registries, self.project, ()) for alias, spec in sorted(data["dependencies"].items())]

        def walk(tasks, packages, roots):
            if not tasks:
                return packages, roots
            parent, alias, request, indexes, base, ancestry = tasks[0]
            last = None
            for release, source in self.candidates(request, indexes, base):
                self.choices += 1
                if self.choices > 2048:
                    raise Error("dependency resolution exceeds 2048 choices; narrow version constraints")
                try:
                    package = self.snapshot(source)
                    name = package["name"]
                    if any(existing.casefold() == name.casefold() and existing != name for existing in packages):
                        raise Conflict(f"case-colliding package identity: {name}")
                    if release and package["version"] != release:
                        raise Error(f"registry version mismatch: {name}, advertised {release}, manifest {package['version']}")
                    if request.get("package", name) != name:
                        raise Error(f"dependency package name mismatch: {alias}")
                    if not matches(package["version"], request.get("version", "*")):
                        raise Conflict(f"dependency version mismatch: {name} requires {request.get('version', '*')}")
                    if name == root_name or name in ancestry:
                        raise Conflict("dependency cycle: " + " -> ".join((*ancestry, name)))
                    next_packages = {key: {**value, "dependencies": dict(value["dependencies"])} for key, value in packages.items()}
                    next_roots = dict(roots)
                    if name in packages:
                        existing = packages[name]
                        if existing["version"] != package["version"] or existing["source"] != package["source"] or existing["source_sha256"] != package["source_sha256"]:
                            raise Conflict(f"conflicting package identity or version: {name}")
                        children = []
                    else:
                        if len(packages) >= 256 or len(ancestry) >= 64:
                            raise Error("dependency graph exceeds 256 packages or 64 levels")
                        next_packages[name] = {**package, "dependencies": {}}
                        child_indexes = {**indexes, **package["_registries"]}
                        child_requests = dict(package["_requests"])
                        for child_alias, entry in package["_data"].get("dependencies", {}).items():
                            if child_alias not in child_requests:
                                child_requests[child_alias] = {**package["_local"][child_alias],
                                    **{k: v for k, v in entry.items() if k in {"package", "version"}}}
                        children = [(name, key, spec, child_indexes, package["_directory"], (*ancestry, name))
                                    for key, spec in sorted(child_requests.items())]
                    if parent is None:
                        next_roots[alias] = name
                    else:
                        next_packages[parent]["dependencies"][alias] = name
                    return walk(children + tasks[1:], next_packages, next_roots)
                except Conflict as exc:
                    last = exc
            raise last or Conflict("cannot resolve dependency graph")

        packages, roots = walk(pending, {}, {})
        lock = {"format": 1, "request_sha256": digest(data), "root_dependencies": roots,
                "packages": [{k: v for k, v in package.items() if not k.startswith("_")}
                             for _, package in sorted(packages.items())]}
        return lock

    def locked_objects(self, lock):
        for package in lock["packages"]:
            directory = self.cache / "objects" / package["source_sha256"]
            if directory.exists():
                if files_at(directory) != package["files"]:
                    raise Error(f"corrupt package cache: {package['name']}")
                continue
            source = package["source"]
            if "path" in source and not Path(source["path"]).is_dir():
                # Local SDK installations can relocate between machines. A
                # current local registry may recover exactly the locked content;
                # no remote query, version upgrade or fingerprint drift occurs.
                source = None
                for location in {"builtin", *self.active_registries.values()}:
                    normalized = normalize_location(location, self.project)
                    if urlparse(normalized).scheme in {"http", "https"}:
                        continue
                    index, base = self.registry(normalized)
                    entry = index["packages"].get(package["name"], {}).get("versions", {}).get(package["version"])
                    if entry and "path" in entry["source"]:
                        candidate = source_spec(entry["source"], base)
                        if Path(candidate["path"]).is_dir():
                            found = self.snapshot(candidate)
                            if found["files"] == package["files"]:
                                source = candidate
                                break
                if source is None:
                    raise Error(f"locked local source is unavailable: {package['name']}")
            recovered = self.snapshot(source)
            if recovered["name"] != package["name"] or recovered["version"] != package["version"] or recovered["files"] != package["files"]:
                raise Error(f"locked package content changed: {package['name']}")

    def validate_lock(self, lock):
        if not isinstance(lock, dict) or type(lock.get("format")) is not int or lock.get("format") != 1 or set(lock) != {"format", "request_sha256", "root_dependencies", "packages"}:
            raise Error("unsupported package lock")
        if not isinstance(lock["packages"], list) or not isinstance(lock["root_dependencies"], dict) or len(lock["packages"]) > 256:
            raise Error("invalid package lock graph")
        if not isinstance(lock["request_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", lock["request_sha256"]):
            raise Error("invalid package request fingerprint")
        names = set()
        for item in lock["packages"]:
            if not isinstance(item, dict) or set(item) != {"name", "version", "source", "source_sha256", "files", "dependencies", "installed_sha256"}:
                raise Error("invalid locked package entry")
            name = safe_name(item["name"])
            if name in names:
                raise Error(f"duplicate locked package identity: {name}")
            names.add(name)
            version(item["version"])
            source_spec(item["source"], self.project)
            if "git" in item["source"] and not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", item["source"].get("rev", "")):
                raise Error("package lock must pin Git to a full commit")
            if not isinstance(item["files"], dict) or len(item["files"]) > MAX_FILES:
                raise Error("invalid locked file list")
            for path, value in item["files"].items():
                relative_path(path)
                if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                    raise Error("invalid locked file fingerprint")
            if digest(item["files"]) != item["source_sha256"] or not isinstance(item["installed_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["installed_sha256"]):
                raise Error("invalid locked package fingerprint")
        for dependencies in [lock["root_dependencies"], *(p["dependencies"] for p in lock["packages"])]:
            if not isinstance(dependencies, dict):
                raise Error("invalid locked dependencies")
            for alias, name in dependencies.items():
                safe_name(alias)
                if name not in names:
                    raise Error(f"unknown locked dependency: {name}")
        entries = {p["name"]: p for p in lock["packages"]}
        visited = set()
        def visit(name, active):
            if name in active or len(active) >= 64:
                raise Error("cyclic or excessively deep package lock")
            if name in visited:
                return
            for child in entries[name]["dependencies"].values():
                visit(child, (*active, name))
            visited.add(name)
        for name in lock["root_dependencies"].values():
            visit(name, ())
        if visited != names or len({name.casefold() for name in names}) != len(names):
            raise Error("unreachable or case-colliding locked packages")

    def check_installed(self, lock):
        directory = self.project / ".naru/packages"
        contained(directory, self.project)
        if not directory.exists():
            return False
        marker = directory / ".naru-managed.json"
        contained(marker, directory)
        if not marker.is_file():
            raise Error(f"package directory is not managed by Naru: {directory}")
        owned = json_read(marker)
        if not isinstance(owned, dict) or set(owned) != {"format", "packages"} or owned["format"] != 1:
            raise Error("invalid installed package marker")
        expected = {p["name"]: p["installed_sha256"] for p in lock["packages"]}
        if not isinstance(owned["packages"], dict) or owned["packages"] != expected:
            raise Error("installed package marker differs from package lock")
        for item in directory.iterdir():
            if item.name not in {*expected, ".naru-managed.json"}:
                raise Error(f"unmanaged file in package directory: {item}")
        for name, fingerprint in owned["packages"].items():
            safe_name(name)
            path = directory / name
            contained(path, directory)
            if path.exists() and digest(files_at(path)) != fingerprint:
                raise Error(f"installed package was modified: {name}; preserve your edits before removing its managed copy")
        return owned["packages"] == expected and all((directory / name).is_dir() for name in expected)

    def install(self, lock, data, text, root_data, selection=None):
        self.locked_objects(lock)
        managed = self.project / ".naru"
        stage = managed / ("stage-" + uuid.uuid4().hex)
        contained(stage, self.project)
        stage.mkdir()
        incoming = stage / "packages"
        incoming.mkdir()
        old = stage / "previous-packages"
        target = managed / "packages"
        saved = {name: (self.project / name).read_bytes() if (self.project / name).exists() else None
                 for name in ("Naru.toml", SOURCES, LOCK)}
        switched = False
        try:
            for package in lock["packages"]:
                destination = incoming / safe_name(package["name"])
                copy_files(self.cache / "objects" / package["source_sha256"], destination, package["files"])
                source_text, source_data = manifest(destination / "Naru.toml")
                deps = {alias: {"path": "../" + name, "package": name,
                               "version": next(p["version"] for p in lock["packages"] if p["name"] == name)}
                        for alias, name in package["dependencies"].items()}
                atomic(destination / "Naru.toml", rewrite_dependencies(source_text, deps))
                installed = digest(files_at(destination))
                if "installed_sha256" in package and package["installed_sha256"] != installed:
                    raise Error(f"locked materialized package differs: {package['name']}")
                package["installed_sha256"] = installed
            atomic(incoming / ".naru-managed.json", json_text({"format": 1, "packages": {p["name"]: p["installed_sha256"] for p in lock["packages"]}}))
            root_deps = dict(root_data.get("dependencies", {}))
            for alias, name in lock["root_dependencies"].items():
                root_deps[alias] = {"path": ".naru/packages/" + name, "package": name,
                                    "version": next(p["version"] for p in lock["packages"] if p["name"] == name)}
            app_text = rewrite_dependencies(text, root_deps)
            if selection:
                alias, modules = selection
                _, selected = manifest(incoming / lock["root_dependencies"][alias] / "Naru.toml")
                for name in modules:
                    if name not in selected.get("exports", {}):
                        raise Error(f"unknown dialect export: {name}")
                app_text = select_dialects(app_text, root_data, alias, modules)
            if target.exists():
                target.rename(old)
            incoming.rename(target)
            switched = True
            atomic(self.project / "Naru.toml", app_text)
            atomic(self.project / SOURCES, json_text(data))
            atomic(self.project / LOCK, json_text(lock))
        except Exception:
            if switched:
                remove_tree(target, managed)
            if old.exists():
                old.rename(target)
            for name, content in saved.items():
                if content is None:
                    (self.project / name).unlink(missing_ok=True)
                else:
                    temporary = self.project / (name + ".rollback")
                    temporary.write_bytes(content)
                    os.replace(temporary, self.project / name)
            raise
        finally:
            remove_tree(stage, managed)

    def fetch(self, *, locked=False, update=False, replacement=None, selection=None):
        with project_guard(self.project):
            if update:
                self.registry_cache.clear()
                self.snapshots.clear()
            text, root_data = manifest(self.project / "Naru.toml")
            data, registries = config(self.project / SOURCES)
            if replacement is not None:
                data = replacement
                registries = {alias: normalize_location(location, self.project)
                              for alias, location in data.get("registries", {"default": "builtin"}).items()}
            # Enroll existing local dependencies so a new remote library can
            # reuse the same package identity (not a second physical checkout).
            # The source path remains in the JSON request; only its compiler
            # materialization changes. Local source edits are adopted by update.
            for alias, entry in root_data.get("dependencies", {}).items():
                if alias not in data["dependencies"]:
                    if entry["path"].replace("\\", "/").startswith(".naru/packages/"):
                        raise Error(f"managed dependency {alias} has no source declaration in {SOURCES}")
                    data["dependencies"][alias] = {key: value for key, value in entry.items() if key in {"path", "package", "version"}}
            self.active_registries = registries
            lock_exists = (self.project / LOCK).exists()
            old = json_read(self.project / LOCK) if lock_exists else None
            if lock_exists:
                self.validate_lock(old)
                self.check_installed(old)
            elif (self.project / ".naru/packages").exists():
                raise Error("package directory is not managed by a package lock; preserve its contents before fetching")
            valid = old and old["request_sha256"] == digest(data)
            if locked and not valid:
                raise Error("Naru.packages.lock is missing or out of date; run naru pkg fetch")
            if valid and not update:
                lock = old
            else:
                lock = self.resolve(data, registries, root_data)
            if valid and not update and self.check_installed(lock):
                self.locked_objects(lock)
                # A hand-edited compiler path must never silently bypass source locks.
                for alias, name in lock["root_dependencies"].items():
                    dep = root_data.get("dependencies", {}).get(alias, {})
                    if dep != {"path": ".naru/packages/" + name, "package": name,
                               "version": next(p["version"] for p in lock["packages"] if p["name"] == name)}:
                        raise Error(f"managed compiler dependency changed: {alias}; run pkg fetch after restoring its path")
                return lock
            self.install(lock, data, text, root_data, selection)
            return lock


def create_dialect(path, name, module):
    safe_name(name)
    if not MODULE.fullmatch(module):
        raise Error(f"invalid rule module name: {module}")
    if path.exists() and any(path.iterdir()):
        raise Error("dialect template destination must be empty")
    path.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / "templates/dialect").rglob("*"):
        if source.is_file():
            target = path / source.relative_to(ROOT / "templates/dialect")
            target.parent.mkdir(parents=True, exist_ok=True)
            text = source.read_text(encoding="utf-8").replace("__PACKAGE_NAME__", name).replace("__MODULE_NAME__", module)
            target.write_text(text, encoding="utf-8", newline="\n")


def package_cli(arguments):
    # Accept global options both before and after a subcommand.
    common, rest = [], []
    index = 0
    while index < len(arguments):
        item = arguments[index]
        if item in {"--project", "--cache"}:
            if index + 1 == len(arguments):
                raise Error(f"missing value for {item}")
            common.extend(arguments[index:index + 2])
            index += 2
        elif item == "--offline":
            common.append(item)
            index += 1
        else:
            rest.append(item)
            index += 1
    arguments = common + rest
    parser = argparse.ArgumentParser(prog="naru pkg", description="Fetch composable dialect libraries from JSON registries or Git repositories.")
    parser.add_argument("--project")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--offline", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="create a dialect library from the bundled template")
    init.add_argument("path", type=Path)
    init.add_argument("--name")
    init.add_argument("--module")
    search = commands.add_parser("search", help="query configured JSON registries")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--registry")
    add = commands.add_parser("add", help="install a named package or repository URL")
    add.add_argument("package")
    add.add_argument("--git", action="store_true", help="treat package as a Git repository (including local paths)")
    add.add_argument("--rev")
    add.add_argument("--subdir", default="")
    add.add_argument("--name", help="dependency alias; package identity is verified from its manifest")
    add.add_argument("--registry")
    add.add_argument("--version", default="*")
    add.add_argument("--dialect", action="append", default=[], help="also select an exported module in language.dialects")
    fetch = commands.add_parser("fetch", help="acquire the locked graph, or resolve a graph without a lock")
    fetch.add_argument("--locked", action="store_true")
    commands.add_parser("update", help="explicitly resolve versions and moving Git refs again")
    commands.add_parser("list", help="list installed package versions and sources")
    registry = commands.add_parser("registry", help="configure a JSON registry location")
    registry.add_argument("name")
    registry.add_argument("location")
    args = parser.parse_args(arguments)
    if args.command == "init":
        name = args.name or args.path.name
        create_dialect(args.path.resolve(), name, args.module or name.replace("-", "_"))
        print(f"Created dialect library: {args.path.resolve()}")
        return 0
    project = project_directory(args.project)
    manager = Manager(project, cache=args.cache, offline=args.offline)
    data, registries = config(project / SOURCES)
    if args.command == "registry":
        safe_name(args.name)
        manager.registry(normalize_location(args.location, project))
        with project_guard(project):
            data.setdefault("registries", {"default": "builtin"})[args.name] = args.location
            atomic(project / SOURCES, json_text(data))
        print(f"Registry {args.name}: {args.location}")
    elif args.command == "search":
        selected = [args.registry] if args.registry else sorted(registries)
        for alias in selected:
            if alias not in registries:
                raise Error(f"unknown registry: {alias}")
            index, _ = manager.registry(registries[alias])
            for name, entry in sorted(index["packages"].items()):
                if args.query.casefold() in (name + " " + entry.get("description", "")).casefold():
                    latest = max(entry["versions"], key=version) if entry["versions"] else "(no releases)"
                    print(f"{alias}/{name}@{latest}  {entry.get('description', '')}")
    elif args.command == "list":
        lock = json_read(project / LOCK)
        manager.validate_lock(lock)
        for package in lock["packages"]:
            print(f"{package['name']}@{package['version']}  {json.dumps(package['source'], ensure_ascii=False)}")
    elif args.command == "add":
        is_git = args.git or urlparse(args.package).scheme in {"https", "ssh", "http"} or re.fullmatch(r"[\w.-]+@[\w.-]+:[\w./-]+", args.package)
        if is_git:
            request = {"git": args.package, "rev": args.rev or "HEAD", "subdir": args.subdir, "version": args.version}
            if args.registry:
                raise Error("Git add cannot select a registry")
            acquired = manager.snapshot(source_spec({k: v for k, v in request.items() if k != "version"}, project))
            request["package"] = acquired["name"]
        else:
            if args.rev or args.subdir:
                raise Error("revision and subdir require a Git source")
            name, separator, constraint = args.package.partition("@")
            safe_name(name)
            request = {"package": name, "version": constraint if separator else args.version}
            if args.registry:
                request["registry"] = args.registry
        alias = safe_name(args.name or request["package"])
        _, root_data = manifest(project / "Naru.toml")
        if alias in root_data.get("dependencies", {}) or alias in data["dependencies"]:
            raise Error(f"dependency alias already exists: {alias}; edit {SOURCES} and run pkg update to change its source")
        data["dependencies"][alias] = request
        lock = manager.fetch(replacement=data, selection=(alias, args.dialect) if args.dialect else None)
        print(f"Installed {request['package']} as {alias}; {len(lock['packages'])} packages locked")
    else:
        lock = manager.fetch(locked=getattr(args, "locked", False), update=args.command == "update")
        print(f"{len(lock['packages'])} packages ready ({LOCK})")
    return 0


def protect_package_outputs(manager, arguments):
    paths = []
    for index, flag in enumerate(arguments):
        if flag in {"-o", "--report"} and index + 1 < len(arguments):
            paths.append(Path(arguments[index + 1]).resolve())
    if arguments[0] == "build" and "-o" not in arguments:
        _, data = manifest(manager.project / "Naru.toml")
        if "output" in data.get("build", {}):
            paths.append((manager.project / data["build"]["output"]).resolve())
    protected = [manager.project / SOURCES, manager.project / LOCK, manager.project / ".naru/pkg.guard"]
    directories = [manager.project / ".naru/packages", manager.cache]
    for output in paths:
        for source in protected:
            if output == source.resolve() or output.exists() and source.exists() and os.path.samefile(output, source):
                raise Error(f"output would overwrite package metadata: {output}")
        if any(output.is_relative_to(directory.resolve()) for directory in directories):
            raise Error(f"output would overwrite a package or its cache: {output}")


def main(arguments=None):
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    try:
        if arguments and arguments[0] == "pkg":
            return package_cli(arguments[1:])
        if arguments and arguments[0] in {"build", "resolve", "freeze", "check", "parse", "emit"}:
            explicit = arguments[arguments.index("--project") + 1] if "--project" in arguments else None
            try:
                project = project_directory(explicit)
            except Error:
                if explicit:
                    raise
                project = None
            if project and (project / SOURCES).is_file():
                offline = "--offline" in arguments
                if offline:
                    arguments.remove("--offline")
                manager = Manager(project, offline=offline)
                protect_package_outputs(manager, arguments)
                manager.fetch(locked="--locked" in arguments)
        compiler = Path(os.environ.get("NARU_COMPILER", ROOT / "target/naru.exe"))
        if not compiler.is_file():
            compiler = ROOT / "naru.exe"
        if not compiler.is_file():
            raise Error("Naru compiler not found; set NARU_COMPILER or build the compiler")
        return subprocess.call([str(compiler), *arguments])
    except (Error, OSError, ValueError, IndexError) as exc:
        print(f"naru pkg: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
