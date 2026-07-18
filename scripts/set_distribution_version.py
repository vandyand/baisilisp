#!/usr/bin/env python3
"""Set the PEP 621 project version in a CI checkout.

Release builds use the version declared in ``pyproject.toml``. Development
builds use the same next-release base with a unique ``.devN`` suffix, without
committing that generated version back to the repository.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: set_distribution_version.py VERSION")

    version = sys.argv[1]
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?:\.dev[0-9]+)?", version):
        raise SystemExit(f"unsupported distribution version: {version!r}")

    cargo_version = re.sub(r"\.dev([0-9]+)$", r"-dev.\1", version)

    for path, package_version in (
        (Path("pyproject.toml"), version),
        (Path("rust/Cargo.toml"), cargo_version),
    ):
        contents = path.read_text(encoding="utf-8")
        updated, replacements = re.subn(
            r'(?m)^version = "[^"]+"$',
            f'version = "{package_version}"',
            contents,
            count=1,
        )
        if replacements != 1:
            raise SystemExit(f"could not locate exactly one package version in {path}")
        path.write_text(updated, encoding="utf-8")

    lockfile = Path("rust/Cargo.lock")
    contents = lockfile.read_text(encoding="utf-8")
    updated, replacements = re.subn(
        r'(?ms)(\[\[package\]\]\nname = "basilisp-native"\nversion = )"[^"]+"',
        rf'\1"{cargo_version}"',
        contents,
        count=1,
    )
    if replacements != 1:
        raise SystemExit(
            "could not locate the Basilisp native package version in Cargo.lock"
        )
    lockfile.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
