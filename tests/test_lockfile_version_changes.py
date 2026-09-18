import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(
    os.environ.get(
        "LOCKFILE_VERSION_CHANGES_SCRIPT",
        Path(__file__).parents[1]
        / "actions"
        / "lockfile-version-changes"
        / "lockfile_version_changes.py",
    )
)
SPEC = importlib.util.spec_from_file_location("lockfile_version_changes", SCRIPT)
assert SPEC and SPEC.loader
lockfiles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lockfiles)


class LockfileVersionChangesTests(unittest.TestCase):
    def test_parses_mise_versions_and_python_build_tags(self) -> None:
        content = """
[tools]
node = [{ version = "22.1.0" }]
python = [{ version = "3.13.1", "platforms.linux-x64" = { url = "https://github.com/astral-sh/python-build-standalone/releases/download/20250101/cpython.tar.gz" } }]
"""

        self.assertEqual(
            lockfiles.mise_versions(content),
            {
                "node": frozenset({"22.1.0"}),
                "python": frozenset({"3.13.1+20250101"}),
            },
        )

    def test_parses_uv_and_pnpm_versions(self) -> None:
        uv = """
[[package]]
name = "httpx"
version = "0.28.0"
[[package]]
name = "local-project"
source = { editable = "." }
"""
        pnpm = """
lockfileVersion: '9.0'
packages:
  '@scope/package@2.0.0(peer@1.0.0)':
    resolution: {}
  plain@1.2.3:
    resolution: {}
snapshots:
  ignored@9.9.9:
    resolution: {}
"""

        self.assertEqual(lockfiles.uv_versions(uv), {"httpx": frozenset({"0.28.0"})})
        self.assertEqual(
            lockfiles.pnpm_versions(pnpm),
            {
                "@scope/package": frozenset({"2.0.0"}),
                "plain": frozenset({"1.2.3"}),
            },
        )

    def test_parses_cargo_and_npm_versions(self) -> None:
        cargo = """
[[package]]
name = "serde"
version = "1.0.200"
[[package]]
name = "syn"
version = "1.0.109"
[[package]]
name = "syn"
version = "2.0.60"
"""
        npm = """
{
  "lockfileVersion": 3,
  "packages": {
    "": {"name": "application", "version": "1.0.0"},
    "node_modules/@scope/package": {"version": "2.0.0"},
    "node_modules/parent/node_modules/package": {"version": "1.2.3"},
    "packages/workspace": {"name": "workspace", "version": "0.1.0"}
  }
}
"""

        self.assertEqual(
            lockfiles.cargo_versions(cargo),
            {
                "serde": frozenset({"1.0.200"}),
                "syn": frozenset({"1.0.109", "2.0.60"}),
            },
        )
        self.assertEqual(
            lockfiles.npm_versions(npm),
            {
                "@scope/package": frozenset({"2.0.0"}),
                "package": frozenset({"1.2.3"}),
                "workspace": frozenset({"0.1.0"}),
            },
        )

    def test_parses_legacy_npm_versions(self) -> None:
        npm = """
{
  "lockfileVersion": 1,
  "dependencies": {
    "my-react": {"version": "npm:react@18.3.1"},
    "parent": {
      "version": "2.0.0",
      "dependencies": {"nested": {"version": "1.2.3"}}
    }
  }
}
"""

        self.assertEqual(
            lockfiles.npm_versions(npm),
            {
                "react": frozenset({"18.3.1"}),
                "parent": frozenset({"2.0.0"}),
                "nested": frozenset({"1.2.3"}),
            },
        )

    def test_parses_legacy_pnpm_package_keys(self) -> None:
        pnpm = """
lockfileVersion: 5.4
packages:
  /react/18.3.1:
    resolution: {}
  /@scope/package/2.0.0:
    resolution: {}
  /modern@3.0.0:
    resolution: {}
"""

        self.assertEqual(
            lockfiles.pnpm_versions(pnpm),
            {
                "react": frozenset({"18.3.1"}),
                "@scope/package": frozenset({"2.0.0"}),
                "modern": frozenset({"3.0.0"}),
            },
        )

    def test_classifies_version_changes(self) -> None:
        classify = lockfiles.version_change
        self.assertEqual(classify(frozenset({"1.2.3"}), frozenset({"2.0.0"})), "major")
        self.assertEqual(classify(frozenset({"1.2.3"}), frozenset({"1.3.0"})), "minor")
        self.assertEqual(classify(frozenset({"1.2.3"}), frozenset({"1.2.4"})), "patch")
        self.assertEqual(
            classify(frozenset({"3.13.1+one"}), frozenset({"3.13.1+two"})),
            "build refresh",
        )
        self.assertEqual(classify(frozenset(), frozenset({"1.0.0"})), "added")

    def test_reads_direct_dependencies(self) -> None:
        pyproject = """
[project]
dependencies = ["HTTPX>=0.28"]
[dependency-groups]
test = ["pytest", { include-group = "lint" }]
"""
        package_json = """
{"dependencies":{"react":"19","my-preact":"npm:preact@10","alias":"npm:@scope/real"},"devDependencies":{"vitest":"3"}}
"""

        self.assertEqual(
            lockfiles.python_direct_dependencies(pyproject), {"httpx", "pytest"}
        )
        self.assertEqual(
            lockfiles.node_direct_dependencies(package_json),
            {"react", "preact", "@scope/real", "vitest"},
        )

    def test_reads_cargo_direct_dependencies(self) -> None:
        cargo_toml = """
[dependencies]
serde = "1"
renamed = { package = "actual-package", version = "2" }
[workspace.dependencies]
workspace_crate = "3"
[target.'cfg(unix)'.build-dependencies]
native_dep = "4"
"""

        self.assertEqual(
            lockfiles.cargo_direct_dependencies(cargo_toml),
            {"serde", "actual-package", "workspace-crate", "native-dep"},
        )


    def test_formats_markdown_summary(self) -> None:
        before = {
            "uv.lock": '[[package]]\nname = "httpx"\nversion = "0.27.0"\n',
            "Cargo.lock": '[[package]]\nname = "serde"\nversion = "1.0.0"\n',
            "package-lock.json": '{"packages":{"node_modules/vitest":{"version":"2.0.0"}}}',
            "pnpm-lock.yaml": "packages:\n  react@18.3.1:\n    resolution: {}\n",
        }
        after = {
            "uv.lock": '[[package]]\nname = "httpx"\nversion = "0.28.0"\n',
            "Cargo.lock": '[[package]]\nname = "serde"\nversion = "1.0.1"\n',
            "package-lock.json": '{"packages":{"node_modules/vitest":{"version":"3.0.0"}}}',
            "pnpm-lock.yaml": "packages:\n  react@19.0.0:\n    resolution: {}\n",
        }

        summary = lockfiles.markdown_summary(
            before,
            after,
            {
                "uv.lock": {"httpx"},
                "Cargo.lock": {"serde"},
                "package-lock.json": {"vitest"},
                "pnpm-lock.yaml": {"react"},
            },
        )

        self.assertIn("### `uv.lock`", summary)
        self.assertIn("| `httpx` | `0.27.0` | `0.28.0` | **minor** | direct |", summary)
        self.assertIn("### `Cargo.lock`", summary)
        self.assertIn("| `serde` | `1.0.0` | `1.0.1` | patch | direct |", summary)
        self.assertIn("### `package-lock.json`", summary)
        self.assertIn("| `vitest` | `2.0.0` | `3.0.0` | **major** | direct |", summary)
        self.assertIn("| `react` | `18.3.1` | `19.0.0` | **major** | direct |", summary)

    def test_reports_no_changes(self) -> None:
        self.assertEqual(
            lockfiles.markdown_summary({}, {}),
            "## Lockfile version changes\n\nNo resolved package version changes.",
        )

    def test_reads_manifests_from_a_revision(self) -> None:
        manifests = {
            "python/pyproject.toml": '[project]\ndependencies = ["httpx"]\n',
            "web/package.json": '{"dependencies":{"react":"19"}}',
            "rust/Cargo.toml": '[dependencies]\nserde = "1"\n',
        }
        with (
            mock.patch.object(lockfiles, "git_tree_files", return_value=list(manifests)),
            mock.patch.object(lockfiles, "git_file", side_effect=lambda _, path: manifests[path]),
        ):
            direct = lockfiles.git_direct_dependencies("revision")

        self.assertEqual(direct["uv.lock"], {"httpx"})
        self.assertEqual(direct["package-lock.json"], {"react"})
        self.assertEqual(direct["Cargo.lock"], {"serde"})

    def test_uses_a_collision_safe_github_output_delimiter(self) -> None:
        summary = "untrusted\nEOF\nmessage<<EOF\nreplacement"
        with tempfile.NamedTemporaryFile() as output:
            lockfiles.write_github_output(output.name, summary)
            content = Path(output.name).read_text(encoding="utf-8")

        first_line, *_, last_line = content.splitlines()
        delimiter = first_line.removeprefix("message<<")
        self.assertNotEqual(delimiter, "EOF")
        self.assertEqual(last_line, delimiter)
        self.assertIn(summary, content)

    def test_escapes_untrusted_markdown_table_values(self) -> None:
        before = {
            "package-lock.json": json.dumps(
                {
                    "packages": {
                        "node_modules/package": {
                            "name": "package|name",
                            "version": "1.0.0",
                        }
                    }
                }
            )
        }
        after = {
            "package-lock.json": json.dumps(
                {
                    "packages": {
                        "node_modules/package": {
                            "name": "package|name",
                            "version": "2.0.0\n```\n## Reviewer notice",
                        }
                    }
                }
            )
        }

        summary = lockfiles.markdown_summary(before, after)

        self.assertIn("package\\|name", summary)
        self.assertNotIn("\n## Reviewer notice", summary)
        self.assertIn(r"\n## Reviewer notice", summary)


if __name__ == "__main__":
    unittest.main()
