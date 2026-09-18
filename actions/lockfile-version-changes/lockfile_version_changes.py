"""Summarize resolved version changes between two revisions' lockfiles."""

import argparse
import json
import os
import re
import shutil
import subprocess  # noqa: S404 - Git reads immutable revisions without a shell.
import tomllib
import uuid
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

LOCK_FILES = (
    "mise.lock",
    "uv.lock",
    "Cargo.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
)
MISE_ENV_LOCK_FILE = re.compile(r"^mise\..+\.lock$")
NUMERIC_VERSION = re.compile(r"^(\d+(?:\.\d+)*)(.*)$")
DEPENDENCY_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
GITHUB_RELEASE_DOWNLOAD = re.compile(
    r"^https://github\.com/[^/]+/[^/]+/releases/download/([^/]+)/"
)


def version_sets(entries: list[tuple[str, str]]) -> dict[str, frozenset[str]]:
    versions: defaultdict[str, set[str]] = defaultdict(set)
    for package, version in entries:
        versions[package].add(version)
    return {package: frozenset(version) for package, version in versions.items()}


def github_release_tag(entry: object) -> str | None:
    if not isinstance(entry, dict):
        return None
    if isinstance(url := entry.get("url"), str) and (
        match := GITHUB_RELEASE_DOWNLOAD.match(url)
    ):
        return match.group(1)
    return None


def mise_entry_versions(tool: str, entry: dict[str, object]) -> list[str]:
    if isinstance(version := entry.get("version"), str):
        platform_tags = {
            tag
            for key, platform in entry.items()
            if key.startswith("platforms.")
            and (tag := github_release_tag(platform)) is not None
        }
        # CPython's version is stable across standalone artifact rebuilds. Include
        # its release tag; other tools' build suffixes are package-defined.
        if tool == "python" and platform_tags:
            return [f"{version}+{tag}" for tag in platform_tags]
        return [version]
    return [tag] if (tag := github_release_tag(entry)) is not None else []


def mise_versions(content: str) -> dict[str, frozenset[str]]:
    if not content:
        return {}
    tools = tomllib.loads(content).get("tools", {})
    return version_sets(
        [
            (tool, version)
            for tool, entries in tools.items()
            for entry in (entries if isinstance(entries, list) else [entries])
            for version in mise_entry_versions(tool, entry)
        ]
    )


def uv_versions(content: str) -> dict[str, frozenset[str]]:
    if not content:
        return {}
    packages = tomllib.loads(content).get("package", [])
    return version_sets(
        [(package["name"], package["version"]) for package in packages if "version" in package]
    )


def cargo_versions(content: str) -> dict[str, frozenset[str]]:
    if not content:
        return {}
    packages = tomllib.loads(content).get("package", [])
    return version_sets(
        [(package["name"], package["version"]) for package in packages if "version" in package]
    )


def npm_versions(content: str) -> dict[str, frozenset[str]]:
    if not content:
        return {}
    data = json.loads(content)
    packages: list[tuple[str, str]] = []
    for path, package in data.get("packages", {}).items():
        if not path or not isinstance(package, dict):
            continue
        name = package.get("name")
        if not isinstance(name, str) and "node_modules/" in path:
            name = path.rsplit("node_modules/", maxsplit=1)[1]
        if isinstance(name, str) and isinstance(version := package.get("version"), str):
            packages.append((name, version))
    if "packages" not in data:
        packages.extend(npm_legacy_versions(data.get("dependencies")))
    return version_sets(packages)


def npm_legacy_versions(dependencies: object) -> list[tuple[str, str]]:
    if not isinstance(dependencies, dict):
        return []
    packages: list[tuple[str, str]] = []
    for name, package in dependencies.items():
        if not isinstance(package, dict):
            continue
        if isinstance(version := package.get("version"), str):
            alias = npm_alias(version)
            packages.append(alias if alias and alias[1] else (name, version))
        packages.extend(npm_legacy_versions(package.get("dependencies")))
    return packages


def npm_alias(specifier: str) -> tuple[str, str | None] | None:
    if not specifier.startswith("npm:"):
        return None
    target = specifier.removeprefix("npm:")
    separator = (
        target.find("@", target.find("/") + 1)
        if target.startswith("@")
        else target.find("@")
    )
    if separator == -1:
        return target, None
    return target[:separator], target[separator + 1 :]


def pnpm_package_version(key: str) -> tuple[str, str] | None:
    key = key.split("(", maxsplit=1)[0]
    if not key.startswith("/"):
        package, separator, version = key.rpartition("@")
    else:
        key = key.removeprefix("/")
        if "@" not in key or (key.startswith("@") and key.count("@") == 1):
            if key.startswith("@"):
                match = re.fullmatch(r"(@[^/]+/[^/]+)/(.+)", key)
                if not match:
                    return None
                package, version = match.groups()
            else:
                package, separator, version = key.partition("/")
        else:
            package, separator, version = key.rpartition("@")
    if not package or not version:
        return None
    return package, version


def pnpm_versions(content: str) -> dict[str, frozenset[str]]:
    if not content:
        return {}
    packages: list[tuple[str, str]] = []
    in_packages = False

    for line in content.splitlines():
        if line == "packages:":
            in_packages = True
            continue
        if in_packages and line and not line.startswith(" "):
            break
        if not in_packages:
            continue

        match = re.fullmatch(r"  (?:'([^']+)'|([^:]+)):", line)
        if not match:
            continue
        if parsed := pnpm_package_version(match.group(1) or match.group(2)):
            packages.append(parsed)

    return version_sets(packages)


PARSERS: dict[str, Callable[[str], dict[str, frozenset[str]]]] = {
    "uv.lock": uv_versions,
    "Cargo.lock": cargo_versions,
    "package-lock.json": npm_versions,
    "pnpm-lock.yaml": pnpm_versions,
}


def lockfile_parser(lock_file: str) -> Callable[[str], dict[str, frozenset[str]]]:
    if lock_file == "mise.lock" or MISE_ENV_LOCK_FILE.fullmatch(lock_file):
        return mise_versions
    return PARSERS[lock_file]


def format_versions(versions: frozenset[str]) -> str:
    return ", ".join(sorted(versions))


def markdown_code(value: str) -> str:
    value = value.replace("\r", r"\r").replace("\n", r"\n").replace("|", r"\|")
    longest_run = max((len(run) for run in re.findall(r"`+", value)), default=0)
    delimiter = "`" * (longest_run + 1)
    return f"{delimiter}{value}{delimiter}"


def format_change(before: frozenset[str], after: frozenset[str]) -> tuple[str, str]:
    if not before:
        return "-", format_versions(after)
    if not after:
        return format_versions(before), "removed"
    return format_versions(before), format_versions(after)


def numeric_version(version: str) -> tuple[tuple[int, ...], str] | None:
    if not (match := NUMERIC_VERSION.fullmatch(version)):
        return None
    return tuple(map(int, match.group(1).split("."))), match.group(2)


def version_change(before: frozenset[str], after: frozenset[str]) -> str:
    if not before:
        return "added"
    if not after:
        return "removed"
    if len(before) != 1 or len(after) != 1:
        return "unknown"

    old, new = next(iter(before)), next(iter(after))
    old_version, new_version = numeric_version(old), numeric_version(new)
    if not old_version or not new_version:
        return "unknown"

    old_parts, old_suffix = old_version
    new_parts, new_suffix = new_version
    if old_parts[0] != new_parts[0]:
        return "major"
    if len(old_parts) < 2 or len(new_parts) < 2:
        return "unknown"
    if old_parts[1] != new_parts[1]:
        return "minor"
    if len(old_parts) > 3 or len(new_parts) > 3:
        return "minor" if old_parts != new_parts else "unknown"
    if len(old_parts) > 2 and len(new_parts) > 2 and old_parts[2] != new_parts[2]:
        return "patch"
    if old_suffix != new_suffix:
        if old_suffix.startswith("+") and new_suffix.startswith("+"):
            return "build refresh"
        return "prerelease"
    return "unknown"


def emphasize_change(change: str, before: frozenset[str]) -> str:
    if change in {"added", "removed", "prerelease", "unknown", "major"}:
        return f"**{change}**"
    if change == "minor" and len(before) == 1:
        version = numeric_version(next(iter(before)))
        if version and version[0][0] == 0:
            return f"**{change}**"
    return change


def normalize_python_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: object) -> str | None:
    if isinstance(requirement, str) and (match := DEPENDENCY_NAME.match(requirement)):
        return normalize_python_name(match.group(1))
    return None


def python_direct_dependencies(content: str) -> set[str]:
    data = tomllib.loads(content)
    project = data.get("project", {})
    tool_uv = data.get("tool", {}).get("uv", {})
    requirements = [
        *project.get("dependencies", []),
        *tool_uv.get("dev-dependencies", []),
        *tool_uv.get("constraint-dependencies", []),
        *tool_uv.get("override-dependencies", []),
        *(
            requirement
            for group in project.get("optional-dependencies", {}).values()
            for requirement in group
        ),
        *(
            requirement
            for group in data.get("dependency-groups", {}).values()
            for requirement in group
        ),
    ]
    return {name for requirement in requirements if (name := requirement_name(requirement))}


def node_direct_dependencies(content: str) -> set[str]:
    data = json.loads(content)
    return {
        alias[0]
        if isinstance(specifier, str) and (alias := npm_alias(specifier))
        else package
        for section in (
            "dependencies",
            "devDependencies",
            "optionalDependencies",
            "peerDependencies",
        )
        for package, specifier in data.get(section, {}).items()
    }


def normalize_cargo_name(name: str) -> str:
    return name.replace("_", "-")


def cargo_dependency_table(table: object) -> set[str]:
    if not isinstance(table, dict):
        return set()
    return {
        normalize_cargo_name(
            dependency.get("package", name) if isinstance(dependency, dict) else name
        )
        for name, dependency in table.items()
    }


def cargo_direct_dependencies(content: str) -> set[str]:
    data = tomllib.loads(content)
    direct = {
        dependency
        for section in ("dependencies", "dev-dependencies", "build-dependencies")
        for dependency in cargo_dependency_table(data.get(section))
    }
    direct.update(cargo_dependency_table(data.get("workspace", {}).get("dependencies")))
    for target in data.get("target", {}).values():
        for section in ("dependencies", "dev-dependencies", "build-dependencies"):
            direct.update(cargo_dependency_table(target.get(section)))
    return direct


def manifest_dependencies(files: dict[str, str]) -> dict[str, set[str]]:
    python: set[str] = set()
    node: set[str] = set()
    cargo: set[str] = set()
    for path, content in files.items():
        parts = Path(path).parts
        if path.endswith("pyproject.toml") and not {".git", ".venv"}.intersection(parts):
            python.update(python_direct_dependencies(content))
        elif path.endswith("package.json") and not {".git", "node_modules"}.intersection(parts):
            node.update(node_direct_dependencies(content))
        elif path.endswith("Cargo.toml") and not {".git", "target"}.intersection(parts):
            cargo.update(cargo_direct_dependencies(content))
    return {
        "uv.lock": python,
        "Cargo.lock": cargo,
        "package-lock.json": node,
        "pnpm-lock.yaml": node,
    }


def merge_direct_dependencies(
    before: dict[str, set[str]], after: dict[str, set[str]]
) -> dict[str, set[str]]:
    return {
        lock_file: before.get(lock_file, set()) | after.get(lock_file, set())
        for lock_file in before.keys() | after.keys()
    }


def dependency_source(lock_file: str, package: str, direct: dict[str, set[str]]) -> str:
    if lock_file == "mise.lock" or MISE_ENV_LOCK_FILE.fullmatch(lock_file):
        return "tool"
    if lock_file == "uv.lock":
        package_name = normalize_python_name(package)
    elif lock_file == "Cargo.lock":
        package_name = normalize_cargo_name(package)
    else:
        package_name = package
    return "direct" if package_name in direct.get(lock_file, set()) else "transitive"


def markdown_summary(
    before: dict[str, str],
    after: dict[str, str],
    direct: dict[str, set[str]] | None = None,
) -> str:
    direct = direct or {}
    sections: list[str] = []
    mise_env_lock_files = sorted(
        path
        for path in before.keys() | after.keys()
        if MISE_ENV_LOCK_FILE.fullmatch(path)
    )
    for lock_file in (
        "mise.lock",
        *mise_env_lock_files,
        "uv.lock",
        "Cargo.lock",
        "package-lock.json",
        "pnpm-lock.yaml",
    ):
        parser = lockfile_parser(lock_file)
        old = parser(before.get(lock_file, ""))
        new = parser(after.get(lock_file, ""))
        changes = [
            (
                package,
                *format_change(old.get(package, frozenset()), new.get(package, frozenset())),
                emphasize_change(
                    version_change(
                        old.get(package, frozenset()), new.get(package, frozenset())
                    ),
                    old.get(package, frozenset()),
                ),
                dependency_source(lock_file, package, direct),
            )
            for package in sorted(old.keys() | new.keys())
            if old.get(package, frozenset()) != new.get(package, frozenset())
        ]
        if not changes:
            continue

        rows = "\n".join(
            f"| {markdown_code(package)} | {markdown_code(old_version)} | "
            f"{markdown_code(new_version)} | {change} | {source} |"
            for package, old_version, new_version, change, source in changes
        )
        sections.append(
            f"### `{lock_file}`\n\n"
            "| Package | Before | After | Change | Source |\n"
            f"| --- | --- | --- | --- | --- |\n{rows}"
        )

    if not sections:
        return "## Lockfile version changes\n\nNo resolved package version changes."
    return "## Lockfile version changes\n\n" + "\n\n".join(sections)


def git_executable() -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git must be installed to read lockfiles")
    return git


def git_file(revision: str, path: str) -> str:
    try:
        return subprocess.check_output(  # noqa: S603 - arguments are trusted GitHub data.
            [git_executable(), "show", f"{revision}:{path}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return ""


def git_tree_files(revision: str) -> list[str]:
    return subprocess.check_output(  # noqa: S603 - revision is trusted GitHub data.
        [git_executable(), "ls-tree", "-r", "--name-only", revision], text=True
    ).splitlines()


def git_direct_dependencies(revision: str) -> dict[str, set[str]]:
    manifest_names = {"pyproject.toml", "package.json", "Cargo.toml"}
    paths = [path for path in git_tree_files(revision) if Path(path).name in manifest_names]
    return manifest_dependencies({path: git_file(revision, path) for path in paths})


def git_lock_files(revision: str) -> set[str]:
    root_files = subprocess.check_output(  # noqa: S603 - revision is trusted GitHub data.
        [git_executable(), "ls-tree", "--name-only", revision], text=True
    ).splitlines()
    return set(LOCK_FILES) | {
        path for path in root_files if MISE_ENV_LOCK_FILE.fullmatch(path)
    }


def merge_base(base: str, head: str) -> str:
    """Resolve the commit where the branch forked from the target branch."""
    try:
        return subprocess.check_output(  # noqa: S603 - revisions are trusted GitHub data.
            [git_executable(), "merge-base", base, head],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return base


def write_github_output(path: str, summary: str) -> None:
    delimiter = f"lockfile_summary_{uuid.uuid4().hex}"
    while delimiter in summary:
        delimiter = f"lockfile_summary_{uuid.uuid4().hex}"
    with open(path, "a", encoding="utf-8") as output:
        output.write(f"message<<{delimiter}\n")
        output.write(summary)
        output.write(f"\n{delimiter}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", required=True, help="Git revision to compare from, resolved to its fork point"
    )
    parser.add_argument("--head", required=True, help="Git revision to compare to")
    args = parser.parse_args()

    base = merge_base(args.base, args.head)
    lock_files = git_lock_files(base) | git_lock_files(args.head)
    before = {path: git_file(base, path) for path in lock_files}
    after = {path: git_file(args.head, path) for path in lock_files}
    direct = merge_direct_dependencies(
        git_direct_dependencies(base), git_direct_dependencies(args.head)
    )
    summary = markdown_summary(before, after, direct)

    if github_output := os.environ.get("GITHUB_OUTPUT"):
        write_github_output(github_output, summary)
    else:
        print(summary)


if __name__ == "__main__":
    main()
