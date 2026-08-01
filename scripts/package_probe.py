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
    "basilisp/algo/monads.lpy",
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
algo_monads = importlib.import_module("basilisp.algo.monads")
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
assert callable(algo_monads.m__PLUS__m_seq__PLUS__m)
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

_SMOKE_SOURCE = """
(ns package-probe.sample
  (:require [clojure.string :as str]
            [medley.core :as medley]))

(defn smoke [args]
  (let [merged (medley/deep-merge {:left {:a 1}} {:left {:b 2}})]
    (str (str/join ":" args)
         "|"
         (get-in merged [:left :a])
         "|"
         (get-in merged [:left :b]))))
"""

_SMOKE_CODE = """
(do
  (require '[package-probe.sample :as sample])
  (println (sample/smoke *command-line-args*)))
"""

_EXPECTED_SMOKE_OUTPUT = "left:right|1|2"


def _run(
    command: list[str], *, cwd: Path, capture_output: bool = False
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    return subprocess.run(
        command,
        check=True,
        cwd=cwd,
        text=capture_output,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
    )


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


def _environment_python(environment: Path, os_name: str = os.name) -> Path:
    return environment / ("Scripts/python.exe" if os_name == "nt" else "bin/python")


def _environment_script(environment: Path, script: str, os_name: str = os.name) -> Path:
    suffix = ".exe" if os_name == "nt" else ""
    return environment / (
        f"Scripts/{script}{suffix}" if os_name == "nt" else f"bin/{script}"
    )


def _write_smoke_project(workspace: Path) -> Path:
    project = workspace / "smoke-project"
    source_dir = project / "src" / "package_probe"
    source_dir.mkdir(parents=True, exist_ok=True)
    (project / "pyproject.toml").write_text(
        '[tool.basilisp]\nsource-paths = ["src"]\n',
        encoding="utf-8",
    )
    (source_dir / "sample.lpy").write_text(_SMOKE_SOURCE, encoding="utf-8")
    return project


def _verify_install(uv: str, artifact: Path, environment: Path, workdir: Path) -> None:
    _run([uv, "venv", str(environment), "--python", sys.executable], cwd=workdir)
    python = _environment_python(environment)
    _run([uv, "pip", "install", "--python", str(python), str(artifact)], cwd=workdir)
    _run([str(python), "-c", _VERIFY_INSTALL], cwd=workdir)
    _verify_cli_smoke(environment, workdir)


def _verify_cli_smoke(environment: Path, workdir: Path) -> None:
    project = _write_smoke_project(workdir)
    basilisp = _environment_script(environment, "basilisp")
    result = _run(
        [
            str(basilisp),
            "run",
            "-c",
            _SMOKE_CODE,
            "left",
            "right",
        ],
        cwd=project,
        capture_output=True,
    )
    if _EXPECTED_SMOKE_OUTPUT not in result.stdout.splitlines():
        raise RuntimeError(
            "installed Basilisp CLI smoke output mismatch: "
            f"expected {_EXPECTED_SMOKE_OUTPUT!r}, got {result.stdout!r}"
        )


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

    print(
        "package probe passed: wheel and sdist include source, import cleanly, "
        "and run the installed CLI"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
