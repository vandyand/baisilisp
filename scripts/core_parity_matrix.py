#!/usr/bin/env python3
"""Generate a clojure.core vs basilisp.core public var compatibility matrix."""

from __future__ import annotations

import argparse
import csv
import os
import shlex
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Iterable

CLOJURE_CORE_PUBLICS = (
    "(doseq [n (sort (map name (keys (ns-publics 'clojure.core))))] " "(println n))"
)

BASILISP_CORE_PUBLICS = (
    "(doseq [n (sort (map name (keys (ns-publics 'basilisp.core))))] " "(println n))"
)
CLOJURE_VERSION = "1.12.4"
DEFAULT_CLOJURE_SDEPS = (
    f'{{:deps {{org.clojure/clojure {{:mvn/version "{CLOJURE_VERSION}"}}}}}}'
)


def _default_clojure_command() -> list[str]:
    """Return a Clojure command that works for native and WSL-backed Windows use."""

    if configured := os.environ.get("CLOJURE_COMMAND"):
        return shlex.split(configured)
    if shutil.which("clojure"):
        return ["clojure", "-Sdeps", DEFAULT_CLOJURE_SDEPS, "-M", "-e"]
    if os.name == "nt" and shutil.which("wsl"):
        return [
            "wsl",
            "-d",
            "Ubuntu-24.04",
            "--",
            "clojure",
            "-Sdeps",
            DEFAULT_CLOJURE_SDEPS,
            "-M",
            "-e",
        ]
    return ["clojure", "-Sdeps", DEFAULT_CLOJURE_SDEPS, "-M", "-e"]


def _run_publics_command(command: list[str]) -> set[str]:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"publics command is unavailable: {command[0]}") from exc
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _status(symbol: str, clojure_publics: set[str], basilisp_publics: set[str]) -> str:
    in_clojure = symbol in clojure_publics
    in_basilisp = symbol in basilisp_publics

    if in_clojure and in_basilisp:
        return "shared"
    if in_clojure:
        return "missing-in-basilisp"
    return "basilisp-extension"


def _rows(
    clojure_publics: set[str], basilisp_publics: set[str]
) -> Iterable[dict[str, str]]:
    for symbol in sorted(clojure_publics | basilisp_publics):
        yield {
            "symbol": symbol,
            "clojure_core": str(symbol in clojure_publics).lower(),
            "basilisp_core": str(symbol in basilisp_publics).lower(),
            "status": _status(symbol, clojure_publics, basilisp_publics),
        }


def has_missing_publics(rows: Iterable[dict[str, str]]) -> bool:
    """Return True when a Clojure core public Var is absent from Basilisp."""

    return any(row["status"] == "missing-in-basilisp" for row in rows)


def main(argv: list[str] | None = None) -> int:
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    parser = argparse.ArgumentParser(
        description="Generate a clojure.core vs basilisp.core public var matrix."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="CSV file to write. Defaults to stdout.",
    )
    parser.add_argument(
        "--basilisp-command",
        default="basilisp run -c",
        help=(
            "command prefix used to evaluate Basilisp (default: 'basilisp run -c'); "
            "quote it when it contains spaces"
        ),
    )
    parser.add_argument(
        "--clojure-command",
        help=(
            "command prefix used to evaluate Clojure; defaults to CLOJURE_COMMAND, "
            f"native clojure with Clojure {CLOJURE_VERSION}, or WSL on Windows"
        ),
    )
    args = parser.parse_args(argv)

    clojure_command = (
        shlex.split(args.clojure_command)
        if args.clojure_command
        else _default_clojure_command()
    )
    clojure_publics = _run_publics_command([*clojure_command, CLOJURE_CORE_PUBLICS])
    basilisp_publics = _run_publics_command(
        [*shlex.split(args.basilisp_command), BASILISP_CORE_PUBLICS]
    )
    rows = list(_rows(clojure_publics, basilisp_publics))

    output = args.output.open("w", newline="") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(
            output,
            fieldnames=("symbol", "clojure_core", "basilisp_core", "status"),
        )
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            output.close()

    missing = len(clojure_publics - basilisp_publics)
    extensions = len(basilisp_publics - clojure_publics)
    shared = len(clojure_publics & basilisp_publics)
    print(
        f"shared={shared} missing_in_basilisp={missing} "
        f"basilisp_extensions={extensions}",
        file=sys.stderr,
    )
    return 1 if has_missing_publics(rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
