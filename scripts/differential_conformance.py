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
DEFAULT_FIXTURE = ROOT / "tests" / "conformance" / "ref_cases.cljc"


def _default_clojure_command() -> str:
    if configured := os.environ.get("CLOJURE_COMMAND"):
        return configured
    if shutil.which("clojure"):
        return "clojure -M -e"
    if os.name == "nt" and shutil.which("wsl"):
        return "wsl -d Ubuntu-24.04 -- clojure -M -e"
    return "clojure -M -e"


def _run(command_prefix: str, source: str, *, label: str) -> list[str]:
    try:
        result = subprocess.run(
            [*shlex.split(command_prefix), source],
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
    return [_normalize_edn(line) for line in result.stdout.splitlines() if line.strip()]


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
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--clojure-command", default=_default_clojure_command())
    parser.add_argument("--basilisp-command", default="uv run basilisp run -c")
    parser.add_argument("--show-output", action="store_true")
    args = parser.parse_args()

    source = "(do\n" + args.fixture.read_text(encoding="utf-8") + "\nnil)"
    clojure = _run(args.clojure_command, source, label="Clojure")
    basilisp = _run(args.basilisp_command, source, label="Basilisp")
    if clojure != basilisp:
        print("Differential conformance mismatch", file=sys.stderr)
        print(f"fixture: {args.fixture}", file=sys.stderr)
        print(f"Clojure:  {clojure!r}", file=sys.stderr)
        print(f"Basilisp: {basilisp!r}", file=sys.stderr)
        return 1
    if args.show_output:
        print("\n".join(basilisp))
    print(f"conformant fixture={args.fixture.name} cases={len(basilisp)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
