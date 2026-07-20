#!/usr/bin/env python3
"""Verify that Maturin packages Basilisp source namespaces correctly."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from zipfile import ZipFile

_REQUIRED_SOURCES = (
    "basilisp/core.lpy",
    "basilisp/datafy.lpy",
    "basilisp/java/io.lpy",
    "basilisp/java/shell.lpy",
    "basilisp/math/combinatorics.lpy",
    "basilisp/spec/alpha.lpy",
)

_VERIFY_INSTALL = """
import importlib
import importlib.metadata
from pathlib import Path

from basilisp.main import init

init()
core = importlib.import_module("basilisp.core")
datafy = importlib.import_module("basilisp.datafy")
java_io = importlib.import_module("basilisp.java.io")
java_shell = importlib.import_module("basilisp.java.shell")
combinatorics = importlib.import_module("basilisp.math.combinatorics")
spec = importlib.import_module("basilisp.spec.alpha")
assert callable(datafy.datafy)
assert callable(java_io.file)
assert callable(java_shell.sh)
assert callable(combinatorics.combinations)
assert callable(spec.valid__Q__)
cache_files = tuple(Path(core.__file__).parent.joinpath("__pycache__").glob("core.*.lpyc"))
assert cache_files, core.__file__
print(importlib.metadata.version("baisilisp"))
print(core.__file__)
print(cache_files[0])
"""


def _run(command: list[str], *, cwd: Path) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, cwd=cwd)


def _assert_wheel_sources(wheel: Path) -> None:
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
    missing = sorted(set(_REQUIRED_SOURCES) - names)
    if missing:
        raise RuntimeError(
            f"wheel is missing Basilisp source file(s): {', '.join(missing)}"
        )


def _assert_sdist_sources(sdist: Path) -> None:
    with tarfile.open(sdist) as archive:
        names = {member.name for member in archive.getmembers() if member.isfile()}
    missing = [
        source
        for source in _REQUIRED_SOURCES
        if not any(name.endswith(f"/{source}") for name in names)
    ]
    if missing:
        raise RuntimeError(
            f"sdist is missing Basilisp source file(s): {', '.join(missing)}"
        )


def _verify_install(uv: str, artifact: Path, environment: Path, workdir: Path) -> None:
    _run([uv, "venv", str(environment), "--python", sys.executable], cwd=workdir)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _run([uv, "pip", "install", "--python", str(python), str(artifact)], cwd=workdir)
    _run([str(python), "-c", _VERIFY_INSTALL], cwd=workdir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and install Basilisp wheel and sdist artifacts in isolation."
    )
    parser.add_argument(
        "--uv",
        default="uv",
        help="uv executable to use for builds and isolated environments (default: uv)",
    )
    args = parser.parse_args()

    uv = shutil.which(args.uv)
    if uv is None:
        parser.error(f"could not find uv executable: {args.uv}")

    repository = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="basilisp-package-probe-") as temp_dir:
        workspace = Path(temp_dir)
        dist = workspace / "dist"
        _run(
            [uv, "build", "--wheel", "--sdist", "--out-dir", str(dist)], cwd=repository
        )

        wheel = next(dist.glob("*.whl"), None)
        sdist = next(dist.glob("*.tar.gz"), None)
        if wheel is None or sdist is None:
            raise RuntimeError("expected one wheel and one source distribution")

        _assert_wheel_sources(wheel)
        _assert_sdist_sources(sdist)
        _verify_install(uv, wheel, workspace / "wheel-venv", workspace)
        _verify_install(uv, sdist, workspace / "sdist-venv", workspace)

    print("package probe passed: wheel and sdist include source and import cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
