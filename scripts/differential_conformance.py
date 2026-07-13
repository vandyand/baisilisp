#!/usr/bin/env python3
"""Run a portable Clojure fixture against Clojure and Basilisp.

Fixtures contain only portable forms and deterministic EDN output. The harness
sends identical source to both runtimes and compares normalized output lines.
It deliberately excludes exception classes, Java objects, and host-specific
formatting from this compatibility boundary.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from basilisp.lang import reader
from basilisp.lang.obj import lrepr

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_DIRECTORY = ROOT / "tests" / "conformance"


def _fixture_paths(fixtures: list[Path] | None) -> list[Path]:
    """Return explicitly selected fixtures or the complete conformance corpus."""

    if fixtures:
        return fixtures
    return sorted(DEFAULT_FIXTURE_DIRECTORY.glob("*_cases.cljc"))


def _fixture_argument(fixture: Path, command_prefix: str) -> str:
    """Render a fixture path for a native or WSL-backed runtime command."""

    resolved = fixture.resolve()
    command = shlex.split(command_prefix)
    if os.name == "nt" and command and command[0].lower() == "wsl":
        drive = resolved.drive.rstrip(":").lower()
        if drive:
            return f"/mnt/{drive}{resolved.as_posix()[2:]}"
    return str(resolved)


def _default_clojure_command() -> str:
    if configured := os.environ.get("CLOJURE_COMMAND"):
        return configured
    if shutil.which("clojure"):
        return "clojure -M"
    if os.name == "nt" and shutil.which("wsl"):
        return "wsl -d Ubuntu-24.04 -- clojure -M"
    return "clojure -M"


def _run(command_prefix: str, fixture_path: str, *, label: str) -> list[str]:
    try:
        result = subprocess.run(
            [*shlex.split(command_prefix), fixture_path],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"{label} command is unavailable: {command_prefix}") from exc
    if result.returncode:
        raise RuntimeError(
            f"{label} fixture failed with exit code {result.returncode}:\n{result.stderr}"
        )
    output = [line for line in result.stdout.splitlines() if line.strip()]
    if not output:
        raise RuntimeError(f"{label} fixture did not emit any EDN cases")
    return [_normalize_edn(line) for line in output]


def _normalize_edn(line: str) -> str:
    """Compare EDN values semantically, not according to map print order."""

    forms = tuple(reader.read_str(line))
    if len(forms) != 1:
        raise RuntimeError(
            f"fixture output must contain exactly one EDN form: {line!r}"
        )
    return lrepr(forms[0])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare deterministic portable fixture output from Clojure and Basilisp."
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        action="append",
        help="Fixture to run; repeat to select multiple fixtures. Defaults to the corpus.",
    )
    parser.add_argument("--clojure-command", default=_default_clojure_command())
    parser.add_argument("--basilisp-command", default="uv run basilisp run")
    parser.add_argument("--show-output", action="store_true")
    args = parser.parse_args()

    fixtures = _fixture_paths(args.fixture)
    if not fixtures:
        parser.error("no conformance fixtures found")

    for fixture in fixtures:
        # Executing the source file, rather than passing it through ``-e``,
        # enables standard .cljc reader-conditionals in Clojure and Basilisp.
        clojure = _run(
            args.clojure_command,
            _fixture_argument(fixture, args.clojure_command),
            label="Clojure",
        )
        basilisp = _run(
            args.basilisp_command,
            _fixture_argument(fixture, args.basilisp_command),
            label="Basilisp",
        )
        if clojure != basilisp:
            print("Differential conformance mismatch", file=sys.stderr)
            print(f"fixture: {fixture}", file=sys.stderr)
            print(f"Clojure:  {clojure!r}", file=sys.stderr)
            print(f"Basilisp: {basilisp!r}", file=sys.stderr)
            return 1
        if args.show_output:
            print("\n".join(basilisp))
        print(f"conformant fixture={fixture.name} cases={len(basilisp)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
