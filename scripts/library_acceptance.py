#!/usr/bin/env python3
"""Prove a multi-file portable library under Clojure and Basilisp.

The runner executes a library-owned ``run.cljc`` entrypoint in both runtimes,
compares its EDN test summary, and validates a checked-in source manifest. It
is deliberately source-led: it neither resolves Maven coordinates nor loads
JARs.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from basilisp import portability
from basilisp.lang import reader
from basilisp.lang.obj import lrepr

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY_ROOT = ROOT / "tests" / "acceptance" / "portable_library"
DEFAULT_MANIFEST = DEFAULT_LIBRARY_ROOT / "portability-manifest.json"
ACCEPTANCE_CONFIG_NAME = "acceptance.json"
_SUBSTITUTIONS = (
    "clojure.set -> basilisp.set",
    "clojure.string -> basilisp.string",
    "clojure.test -> basilisp.test",
    "clojure.walk -> basilisp.walk",
)
_SUPPORTED_PYTHON = ("3.10", "3.11", "3.12", "3.13", "3.14")


def _default_clojure_command() -> str:
    if configured := os.environ.get("CLOJURE_COMMAND"):
        return configured
    if shutil.which("clojure"):
        return "clojure -M"
    if os.name == "nt" and shutil.which("wsl"):
        return "wsl -d Ubuntu-24.04 -- clojure -M"
    return "clojure -M"


def _path_for_command(path: Path, command_prefix: str) -> str:
    """Render an absolute path for native or WSL-backed runtime commands."""

    resolved = path.resolve()
    command = shlex.split(command_prefix)
    if os.name == "nt" and command and command[0].lower() == "wsl":
        drive = resolved.drive.rstrip(":").lower()
        if drive:
            return f"/mnt/{drive}{resolved.as_posix()[2:]}"
    return str(resolved)


def _run(command_prefix: str, runner: Path, *, label: str) -> list[str]:
    try:
        result = subprocess.run(
            [*shlex.split(command_prefix), _path_for_command(runner, command_prefix)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"{label} command is unavailable: {command_prefix}") from exc
    if result.returncode:
        raise RuntimeError(
            f"{label} acceptance run failed with exit code {result.returncode}:\n"
            f"{result.stderr}"
        )
    output = [line for line in result.stdout.splitlines() if line.strip()]
    if not output:
        raise RuntimeError(f"{label} acceptance run did not emit a summary")
    # Test frameworks are free to report human-readable progress. The
    # library-owned runner's final line is the machine-readable EDN contract.
    return [_normalize_edn(output[-1])]


def _normalize_edn(line: str) -> str:
    forms = tuple(reader.read_str(line))
    if len(forms) != 1:
        raise RuntimeError(
            f"acceptance output must contain exactly one EDN form: {line!r}"
        )
    return lrepr(forms[0])


def _acceptance_settings(
    library_root: Path,
) -> tuple[Path, tuple[str, ...], str | None, str | None]:
    """Read optional per-library manifest settings without executing source."""

    config_path = library_root / ACCEPTANCE_CONFIG_NAME
    if not config_path.is_file():
        return library_root, _SUBSTITUTIONS, None, None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid acceptance configuration: {config_path}") from exc
    if not isinstance(config, dict):
        raise RuntimeError(f"acceptance configuration must be an object: {config_path}")
    source_root_setting = config.get("source_root", ".")
    if not isinstance(source_root_setting, str):
        raise RuntimeError(f"acceptance source_root must be a string: {config_path}")
    resolved_library_root = library_root.resolve()
    source_root = (resolved_library_root / source_root_setting).resolve()
    try:
        source_root.relative_to(resolved_library_root)
    except ValueError as exc:
        raise RuntimeError(
            f"acceptance source_root must stay within the library: {config_path}"
        ) from exc
    if not source_root.is_dir():
        raise RuntimeError(f"acceptance source root does not exist: {source_root}")
    substitutions = config.get("substitutions", _SUBSTITUTIONS)
    if not isinstance(substitutions, list) or not all(
        isinstance(substitution, str) for substitution in substitutions
    ):
        raise RuntimeError(f"acceptance substitutions must be strings: {config_path}")
    upstream_url = config.get("upstream_url")
    upstream_revision = config.get("upstream_revision")
    if upstream_url is not None and not isinstance(upstream_url, str):
        raise RuntimeError(f"acceptance upstream_url must be a string: {config_path}")
    if upstream_revision is not None and not isinstance(upstream_revision, str):
        raise RuntimeError(
            f"acceptance upstream_revision must be a string: {config_path}"
        )
    return source_root, tuple(substitutions), upstream_url, upstream_revision


def acceptance_manifest(library_root: Path) -> str:
    """Create a stable manifest for a checked-in acceptance library."""

    source_root, substitutions, upstream_url, upstream_revision = _acceptance_settings(
        library_root
    )
    manifest = portability.inspect_source_tree(
        source_root,
        upstream_url=upstream_url,
        upstream_revision=upstream_revision,
        substitutions=substitutions,
        test_command="uv run python scripts/library_acceptance.py",
        supported_python=_SUPPORTED_PYTHON,
    )
    # Absolute worktree paths are not reviewable artifacts; all source paths in
    # the nested records are already relative to this root.
    return portability.manifest_json(replace(manifest, source_root="."))


def verify_manifest(library_root: Path, manifest_path: Path) -> str:
    """Return the manifest after proving it matches the checked-in artifact."""

    actual = acceptance_manifest(library_root)
    try:
        expected = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"acceptance manifest is missing: {manifest_path}") from exc
    if expected != actual:
        raise RuntimeError(
            "acceptance manifest is stale; regenerate it after reviewing source changes: "
            f"{manifest_path}"
        )
    return actual


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a source-level portable-library acceptance check."
    )
    parser.add_argument("--library-root", type=Path, default=DEFAULT_LIBRARY_ROOT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--clojure-command", default=_default_clojure_command())
    parser.add_argument("--basilisp-command", default="uv run basilisp run")
    parser.add_argument("--show-output", action="store_true")
    parser.add_argument("--show-manifest", action="store_true")
    args = parser.parse_args()

    library_root = args.library_root.resolve()
    manifest_path = (
        args.manifest.resolve()
        if args.manifest is not None
        else library_root / DEFAULT_MANIFEST.name
    )
    runner = library_root / "run.cljc"
    if not runner.is_file():
        parser.error(f"library runner does not exist: {runner}")
    manifest = verify_manifest(library_root, manifest_path)
    clojure = _run(args.clojure_command, runner, label="Clojure")
    basilisp = _run(args.basilisp_command, runner, label="Basilisp")
    if clojure != basilisp:
        print("Portable-library acceptance mismatch", file=sys.stderr)
        print(f"Clojure:  {clojure!r}", file=sys.stderr)
        print(f"Basilisp: {basilisp!r}", file=sys.stderr)
        return 1
    if args.show_output:
        print("\n".join(basilisp))
    if args.show_manifest:
        print(manifest, end="")
    print(
        f"accepted library={library_root.name} classification=portable "
        f"summaries={len(basilisp)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
