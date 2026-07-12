#!/usr/bin/env python3
"""Generate a clojure.core vs basilisp.core public var compatibility matrix."""

from __future__ import annotations

import argparse
import csv
import shlex
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


def _run_publics_command(command: list[str]) -> set[str]:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
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


def main() -> int:
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
    args = parser.parse_args()

    clojure_publics = _run_publics_command(
        ["clojure", "-M", "-e", CLOJURE_CORE_PUBLICS]
    )
    basilisp_publics = _run_publics_command(
        [*shlex.split(args.basilisp_command), BASILISP_CORE_PUBLICS]
    )

    output = args.output.open("w", newline="") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(
            output,
            fieldnames=("symbol", "clojure_core", "basilisp_core", "status"),
        )
        writer.writeheader()
        writer.writerows(_rows(clojure_publics, basilisp_publics))
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
