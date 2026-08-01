#!/usr/bin/env python3
"""Prove a multi-file portable library under Clojure and Basilisp.

The runner executes a library-owned ``run.cljc`` entrypoint in both runtimes,
compares its EDN test summary, and validates a checked-in source manifest. It
is deliberately source-led: it neither resolves Maven coordinates nor loads
JARs.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Mapping

from basilisp import portability
from basilisp.lang import reader
from basilisp.lang.obj import lrepr

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACCEPTANCE_DIRECTORY = ROOT / "tests" / "acceptance"
DEFAULT_LIBRARY_ROOT = ROOT / "tests" / "acceptance" / "portable_library"
DEFAULT_MANIFEST = DEFAULT_LIBRARY_ROOT / "portability-manifest.json"
ACCEPTANCE_CONFIG_NAME = "acceptance.json"
EXPECTED_ACCEPTANCE_LIBRARY_ROOTS = (
    "portable_library",
    "upstream/algo-generic",
    "upstream/algo-monads",
    "upstream/cognitect-anomalies",
    "upstream/core-async",
    "upstream/core-cache-memoize",
    "upstream/core-match",
    "upstream/core-unify",
    "upstream/data-codec-base64",
    "upstream/data-csv",
    "upstream/data-json",
    "upstream/data-priority-map",
    "upstream/data-xml",
    "upstream/math-combinatorics",
    "upstream/medley",
    "upstream/test-check",
    "upstream/tools-cli",
    "upstream/tools-logging",
    "upstream/tools-macro",
    "upstream/tools-namespace",
    "upstream/tools-reader",
)
_SUBSTITUTIONS = (
    "clojure.set -> basilisp.set",
    "clojure.string -> basilisp.string",
    "clojure.test -> basilisp.test",
    "clojure.walk -> basilisp.walk",
)
_SUPPORTED_PYTHON = ("3.10", "3.11", "3.12", "3.13", "3.14")
CLOJURE_VERSION = "1.12.4"
DEFAULT_CLOJURE_SDEPS = (
    f'{{:deps {{org.clojure/clojure {{:mvn/version \\"{CLOJURE_VERSION}\\"}}}}}}'
)


def _clojure_sdeps(extra_deps: Mapping[str, str] | None = None) -> str:
    deps = {
        "org.clojure/clojure": CLOJURE_VERSION,
        **(extra_deps or {}),
    }
    rendered = " ".join(
        f'{artifact} {{:mvn/version \\"{version}\\"}}'
        for artifact, version in sorted(deps.items())
    )
    return f"{{:deps {{{rendered}}}}}"


def _default_clojure_command(
    extra_deps: Mapping[str, str] | None = None,
) -> str:
    sdeps = _clojure_sdeps(extra_deps)
    if configured := os.environ.get("CLOJURE_COMMAND"):
        return configured
    if shutil.which("clojure"):
        return f'clojure -Sdeps "{sdeps}" -M'
    if os.name == "nt" and shutil.which("wsl"):
        return f'wsl -d Ubuntu-24.04 -- clojure -Sdeps "{sdeps}" -M'
    return f'clojure -Sdeps "{sdeps}" -M'


def _path_for_command(path: Path, command_prefix: str) -> str:
    """Render an absolute path for native or WSL-backed runtime commands."""

    resolved = path.resolve()
    command = shlex.split(command_prefix)
    if os.name == "nt" and command and command[0].lower() == "wsl":
        drive = resolved.drive.rstrip(":").lower()
        if drive:
            return f"/mnt/{drive}{resolved.as_posix()[2:]}"
    return resolved.as_posix()


def _run(
    command_prefix: str,
    runner: Path,
    *,
    label: str,
    extra_env: Mapping[str, str] | None = None,
    load_via_code: bool = False,
) -> list[str]:
    env = None
    if extra_env:
        env = os.environ.copy()
        env.update(extra_env)
    command = shlex.split(command_prefix)
    runner_path = _path_for_command(runner, command_prefix)
    if load_via_code:
        code = f'(load-file "{runner_path}")'
        if (
            any(Path(token).name.startswith("basilisp") for token in command)
            and "run" in command
        ):
            command = [*command, "-c", code]
        else:
            command = [*command, "-e", code]
    else:
        command = [*command, runner_path]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            env=env,
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


def _acceptance_settings(
    library_root: Path,
) -> tuple[
    Path,
    tuple[str, ...],
    str | None,
    str | None,
    dict[str, str],
    bool,
]:
    """Read optional per-library manifest settings without executing source."""

    config_path = library_root / ACCEPTANCE_CONFIG_NAME
    if not config_path.is_file():
        return library_root, _SUBSTITUTIONS, None, None, {}, False
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid acceptance configuration: {config_path}") from exc
    if not isinstance(config, dict):
        raise RuntimeError(f"acceptance configuration must be an object: {config_path}")
    source_root_setting = config.get("source_root", ".")
    if not isinstance(source_root_setting, str):
        raise RuntimeError(f"acceptance source_root must be a string: {config_path}")
    resolved_library_root = library_root.resolve()
    source_root = (resolved_library_root / source_root_setting).resolve()
    try:
        source_root.relative_to(resolved_library_root)
    except ValueError as exc:
        raise RuntimeError(
            f"acceptance source_root must stay within the library: {config_path}"
        ) from exc
    if not source_root.is_dir():
        raise RuntimeError(f"acceptance source root does not exist: {source_root}")
    substitutions = config.get("substitutions")
    if substitutions is None:
        substitutions = _SUBSTITUTIONS
    elif not isinstance(substitutions, list) or not all(
        isinstance(substitution, str) for substitution in substitutions
    ):
        raise RuntimeError(f"acceptance substitutions must be strings: {config_path}")
    upstream_url = config.get("upstream_url")
    upstream_revision = config.get("upstream_revision")
    if upstream_url is not None and not isinstance(upstream_url, str):
        raise RuntimeError(f"acceptance upstream_url must be a string: {config_path}")
    if upstream_revision is not None and not isinstance(upstream_revision, str):
        raise RuntimeError(
            f"acceptance upstream_revision must be a string: {config_path}"
        )
    clojure_deps = config.get("clojure_deps", {})
    if not isinstance(clojure_deps, dict) or not all(
        isinstance(artifact, str) and isinstance(version, str)
        for artifact, version in clojure_deps.items()
    ):
        raise RuntimeError(
            f"acceptance clojure_deps must map artifact strings to version strings: {config_path}"
        )
    run_via_load_file = config.get("run_via_load_file", False)
    if not isinstance(run_via_load_file, bool):
        raise RuntimeError(
            f"acceptance run_via_load_file must be a boolean: {config_path}"
        )
    return (
        source_root,
        tuple(substitutions),
        upstream_url,
        upstream_revision,
        clojure_deps,
        run_via_load_file,
    )


def acceptance_manifest(library_root: Path) -> str:
    """Create a stable manifest for a checked-in acceptance library."""

    source_root, substitutions, upstream_url, upstream_revision, _, _ = (
        _acceptance_settings(library_root)
    )
    manifest = portability.inspect_source_tree(
        source_root,
        upstream_url=upstream_url,
        upstream_revision=upstream_revision,
        substitutions=substitutions,
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


def acceptance_library_roots(
    acceptance_directory: Path = DEFAULT_ACCEPTANCE_DIRECTORY,
) -> list[Path]:
    """Return checked-in acceptance libraries in stable execution order."""

    if not acceptance_directory.is_dir():
        raise RuntimeError(
            f"acceptance directory does not exist: {acceptance_directory}"
        )
    return sorted(
        path.parent
        for path in acceptance_directory.rglob("run.cljc")
        if (path.parent / DEFAULT_MANIFEST.name).is_file()
    )


def _relative_acceptance_root(
    library_root: Path, acceptance_directory: Path = DEFAULT_ACCEPTANCE_DIRECTORY
) -> str:
    return library_root.resolve().relative_to(acceptance_directory.resolve()).as_posix()


def acceptance_inventory_errors(
    acceptance_directory: Path = DEFAULT_ACCEPTANCE_DIRECTORY,
) -> list[str]:
    """Return errors when checked-in acceptance libraries drift from the manifest."""

    observed = {
        _relative_acceptance_root(root, acceptance_directory)
        for root in acceptance_library_roots(acceptance_directory)
    }
    expected = set(EXPECTED_ACCEPTANCE_LIBRARY_ROOTS)

    errors: list[str] = []
    unexpected = sorted(observed - expected)
    missing = sorted(expected - observed)
    if unexpected:
        errors.append("unexpected acceptance library root(s): " + ", ".join(unexpected))
    if missing:
        errors.append("missing acceptance library root(s): " + ", ".join(missing))
    return errors


def _shard_library_roots(
    library_roots: list[Path], *, shard_count: int, shard_index: int
) -> list[Path]:
    """Return the stable modulo-selected acceptance-library shard."""

    if shard_count < 1:
        raise ValueError("shard_count must be greater than zero")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard_index must be between 0 and shard_count - 1")
    if shard_count == 1:
        return library_roots
    return [
        library_root
        for index, library_root in enumerate(library_roots)
        if index % shard_count == shard_index
    ]


def _accept_library(
    library_root: Path,
    manifest_path: Path,
    *,
    clojure_command: str,
    basilisp_command: str,
    basilisp_env: Mapping[str, str] | None = None,
    show_output: bool = False,
    show_manifest: bool = False,
    write_manifest: bool = False,
) -> bool:
    runner = library_root / "run.cljc"
    if not runner.is_file():
        raise RuntimeError(f"library runner does not exist: {runner}")
    if write_manifest:
        manifest = acceptance_manifest(library_root)
        manifest_path.write_text(manifest, encoding="utf-8", newline="\n")
    else:
        manifest = verify_manifest(library_root, manifest_path)
    _, _, _, _, clojure_deps, run_via_load_file = _acceptance_settings(library_root)
    if clojure_deps and clojure_command == _default_clojure_command():
        clojure_command = _default_clojure_command(clojure_deps)
    clojure = _run(
        clojure_command,
        runner,
        label="Clojure",
        load_via_code=run_via_load_file,
    )
    basilisp = _run(
        basilisp_command,
        runner,
        label="Basilisp",
        extra_env=basilisp_env,
        load_via_code=run_via_load_file,
    )
    if clojure != basilisp:
        print("Portable-library acceptance mismatch", file=sys.stderr)
        print(f"library: {library_root}", file=sys.stderr)
        print(f"Clojure:  {clojure!r}", file=sys.stderr)
        print(f"Basilisp: {basilisp!r}", file=sys.stderr)
        return False
    if show_output:
        print("\n".join(basilisp))
    if show_manifest:
        print(manifest, end="")
    print(
        f"accepted library={library_root.name} classification=portable "
        f"summaries={len(basilisp)}",
        flush=True,
    )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a source-level portable-library acceptance check."
    )
    parser.add_argument("--library-root", type=Path, default=DEFAULT_LIBRARY_ROOT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--all",
        action="store_true",
        help="run every checked-in acceptance library under tests/acceptance",
    )
    parser.add_argument(
        "--verify-inventory",
        action="store_true",
        help="fail if checked-in acceptance libraries differ from the manifest",
    )
    parser.add_argument("--clojure-command", default=_default_clojure_command())
    parser.add_argument("--basilisp-command", default="uv run basilisp run")
    parser.add_argument(
        "--disable-basilisp-ns-cache",
        action="store_true",
        help=(
            "run Basilisp acceptance libraries with "
            "BASILISP_DO_NOT_CACHE_NAMESPACES=true; useful for proof runs that "
            "should not depend on pre-existing .lpyc state"
        ),
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=1,
        help="split --all acceptance libraries into this many stable modulo shards",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="run only this zero-based --all shard index",
    )
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="replace the checked-in manifest after its generated content is reviewed",
    )
    parser.add_argument("--show-output", action="store_true")
    parser.add_argument("--show-manifest", action="store_true")
    args = parser.parse_args(argv)

    basilisp_env = (
        {"BASILISP_DO_NOT_CACHE_NAMESPACES": "true"}
        if args.disable_basilisp_ns_cache
        else None
    )

    if args.verify_inventory:
        errors = acceptance_inventory_errors()
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        if not args.all:
            return 0

    if args.all:
        if args.manifest is not None:
            parser.error("--manifest cannot be combined with --all")
        try:
            roots = _shard_library_roots(
                acceptance_library_roots(),
                shard_count=args.shard_count,
                shard_index=args.shard_index,
            )
        except ValueError as exc:
            parser.error(str(exc))
        if not roots:
            parser.error("no acceptance libraries found")
        for library_root in roots:
            if not _accept_library(
                library_root.resolve(),
                library_root.resolve() / DEFAULT_MANIFEST.name,
                clojure_command=args.clojure_command,
                basilisp_command=args.basilisp_command,
                basilisp_env=basilisp_env,
                show_output=args.show_output,
                show_manifest=args.show_manifest,
                write_manifest=args.write_manifest,
            ):
                return 1
        return 0

    if args.shard_count != 1 or args.shard_index != 0:
        parser.error("--shard-count and --shard-index require --all")

    library_root = args.library_root.resolve()
    manifest_path = (
        args.manifest.resolve()
        if args.manifest is not None
        else library_root / DEFAULT_MANIFEST.name
    )
    return (
        0
        if _accept_library(
            library_root,
            manifest_path,
            clojure_command=args.clojure_command,
            basilisp_command=args.basilisp_command,
            basilisp_env=basilisp_env,
            show_output=args.show_output,
            show_manifest=args.show_manifest,
            write_manifest=args.write_manifest,
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
