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
    "basilisp/concurrent.lpy",
    "basilisp/datafy.lpy",
    "basilisp/inspector.lpy",
    "basilisp/java/io.lpy",
    "basilisp/java/basis.lpy",
    "basilisp/java/basis/impl.lpy",
    "basilisp/java/browse.lpy",
    "basilisp/java/browse_ui.lpy",
    "basilisp/java/javadoc.lpy",
    "basilisp/java/shell.lpy",
    "basilisp/main_compat.lpy",
    "basilisp/core/match.lpy",
    "basilisp/math/combinatorics.lpy",
    "basilisp/parallel.lpy",
    "basilisp/repl_deps.lpy",
    "basilisp/spec/alpha.lpy",
    "basilisp/test/junit.lpy",
    "basilisp/tools/deps/interop.lpy",
    "medley/core.lpy",
)

_VERIFY_INSTALL = """
import importlib
import importlib.metadata
from pathlib import Path

from basilisp.main import init

init()
core = importlib.import_module("basilisp.core")
concurrent = importlib.import_module("basilisp.concurrent")
datafy = importlib.import_module("basilisp.datafy")
inspector = importlib.import_module("basilisp.inspector")
basis = importlib.import_module("basilisp.java.basis")
basis_impl = importlib.import_module("basilisp.java.basis.impl")
browse = importlib.import_module("basilisp.java.browse")
browse_ui = importlib.import_module("basilisp.java.browse_ui")
java_io = importlib.import_module("basilisp.java.io")
javadoc = importlib.import_module("basilisp.java.javadoc")
java_shell = importlib.import_module("basilisp.java.shell")
main_compat = importlib.import_module("basilisp.main_compat")
core_match = importlib.import_module("basilisp.core.match")
combinatorics = importlib.import_module("basilisp.math.combinatorics")
medley = importlib.import_module("medley.core")
parallel = importlib.import_module("basilisp.parallel")
repl_deps = importlib.import_module("basilisp.repl_deps")
spec = importlib.import_module("basilisp.spec.alpha")
test_junit = importlib.import_module("basilisp.test.junit")
deps_interop = importlib.import_module("basilisp.tools.deps.interop")
assert callable(datafy.datafy)
assert callable(concurrent.chan)
assert callable(concurrent.pipeline__BANG__)
assert callable(inspector.tree_model)
assert callable(basis.current_basis)
assert callable(basis_impl.update_basis__BANG__)
assert callable(browse.browse_url)
assert browse_ui is not None
assert callable(java_io.file)
assert callable(javadoc.javadoc)
assert callable(java_shell.sh)
assert callable(main_compat.repl_read)
assert callable(core_match.match)
assert callable(combinatorics.combinations)
assert callable(medley.deep_merge)
assert callable(parallel.pvec)
assert callable(repl_deps.add_libs)
assert callable(spec.valid__Q__)
assert callable(test_junit.junit_report)
assert callable(deps_interop.invoke_tool)
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
