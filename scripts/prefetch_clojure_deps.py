#!/usr/bin/env python3
"""Prefetch Clojure CLI dependencies with bounded retry.

The parity proof workflow fans differential conformance across many shards.
Fresh runners may otherwise ask Maven Central for the same dependency set at
the same time and occasionally receive HTTP 429 responses before any fixture
has run. This helper resolves the classpath once per job with retry so the
actual proof command fails on semantics, not a transient artifact download.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import differential_conformance, library_acceptance

SDEPS_BY_SOURCE = {
    "differential": differential_conformance.DEFAULT_CLOJURE_SDEPS,
    "library": library_acceptance.DEFAULT_CLOJURE_SDEPS,
}


def _direct_sdeps(sdeps: str) -> str:
    """Return an Sdeps string suitable for direct subprocess argv."""

    return sdeps.replace('\\"', '"')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve Clojure CLI dependencies before parity proof commands."
    )
    parser.add_argument("source", choices=sorted(SDEPS_BY_SOURCE))
    parser.add_argument("--clojure", default="clojure")
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--delay-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)

    command = [
        args.clojure,
        "-Sdeps",
        _direct_sdeps(SDEPS_BY_SOURCE[args.source]),
        "-P",
    ]
    for attempt in range(1, args.attempts + 1):
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"prefetched Clojure dependencies for {args.source}")
            return 0
        if attempt < args.attempts:
            print(
                f"Clojure dependency prefetch attempt {attempt}/{args.attempts} "
                f"failed; retrying in {args.delay_seconds:g}s",
                file=sys.stderr,
            )
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            time.sleep(args.delay_seconds)

    print(
        f"Clojure dependency prefetch failed after {args.attempts} attempts",
        file=sys.stderr,
    )
    if result.stdout:
        print(result.stdout, file=sys.stderr)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
