#!/usr/bin/env python3
"""Prove a multi-file portable library under Clojure and Basilisp.

The runner executes a library-owned ``run.cljc`` entrypoint in both runtimes,
compares its EDN test summary, and validates a checked-in source manifest. It
is deliberately source-led: it neither resolves Maven coordinates nor loads
JARs.
"""

from __future__ import annotations

import argparse
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


def acceptance_manifest(library_root: Path) -> str:
    """Create a stable manifest for a checked-in acceptance library."""

    manifest = portability.inspect_source_tree(
        library_root,
        substitutions=_SUBSTITUTIONS,
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
