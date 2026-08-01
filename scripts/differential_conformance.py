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
from typing import Mapping

from basilisp.lang import reader
from basilisp.lang.obj import lrepr

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_DIRECTORY = ROOT / "tests" / "conformance"
EXPECTED_CONFORMANCE_FIXTURE_NAMES = (
    "agent_context_cases.cljc",
    "base64_cases.cljc",
    "case_cases.cljc",
    "character_cases.cljc",
    "chunk_cases.cljc",
    "compile_vars_cases.cljc",
    "concurrency_cases.cljc",
    "core_async_cases.cljc",
    "core_bit_cases.cljc",
    "core_cache_cases.cljc",
    "core_cases.cljc",
    "core_collection_array_transient_cases.cljc",
    "core_collection_function_cases.cljc",
    "core_concurrency_random_cases.cljc",
    "core_definition_utility_cases.cljc",
    "core_deftype_cases.cljc",
    "core_genclass_cases.cljc",
    "core_gvec_cases.cljc",
    "core_hierarchy_multimethod_cases.cljc",
    "core_host_print_resource_cases.cljc",
    "core_lifecycle_cases.cljc",
    "core_match_cases.cljc",
    "core_memoize_cases.cljc",
    "core_namespace_state_cases.cljc",
    "core_protocols_cases.cljc",
    "core_proxy_interface_cases.cljc",
    "core_public_surface_cases.cljc",
    "core_reader_eval_load_cases.cljc",
    "core_resultset_syntax_cases.cljc",
    "core_runtime_boundary_cases.cljc",
    "core_runtime_representation_cases.cljc",
    "core_sequence_control_cases.cljc",
    "core_server_cases.cljc",
    "core_specs_uuid_cases.cljc",
    "core_stream_cases.cljc",
    "core_text_regex_io_cases.cljc",
    "core_var_binding_cases.cljc",
    "csv_cases.cljc",
    "data_cases.cljc",
    "data_xml_cases.cljc",
    "datafy_cases.cljc",
    "definline_cases.cljc",
    "deps_tooling_cases.cljc",
    "edge_cases.cljc",
    "edn_cases.cljc",
    "exception_cause_cases.cljc",
    "file_var_cases.cljc",
    "hash_cases.cljc",
    "inspector_cases.cljc",
    "instant_cases.cljc",
    "java_browse_cases.cljc",
    "java_classpath_cases.cljc",
    "java_io_cases.cljc",
    "java_javadoc_cases.cljc",
    "json_cases.cljc",
    "junit_cases.cljc",
    "legacy_metadata_cases.cljc",
    "loop_closure_cases.cljc",
    "main_cases.cljc",
    "math_cases.cljc",
    "math_combinatorics_cases.cljc",
    "math_context_cases.cljc",
    "merge_cases.cljc",
    "namespace_alias_cases.cljc",
    "namespace_prefix_cases.cljc",
    "numeric_coercion_cases.cljc",
    "numeric_equality_cases.cljc",
    "parallel_cases.cljc",
    "pprint_cases.cljc",
    "prepl_cases.cljc",
    "primitive_array_cases.cljc",
    "print_helpers_cases.cljc",
    "print_writer_cases.cljc",
    "priority_map_cases.cljc",
    "process_cases.cljc",
    "protocol_cache_cases.cljc",
    "proxy_helpers_cases.cljc",
    "reader_eval_cases.cljc",
    "reducers_cases.cljc",
    "ref_cases.cljc",
    "ref_fuzz_cases.cljc",
    "ref_history_cases.cljc",
    "reflect_cases.cljc",
    "reflect_java_resource_cases.cljc",
    "reflection_warning_vars_cases.cljc",
    "repl_cases.cljc",
    "repl_context_cases.cljc",
    "repl_host_boundary_cases.cljc",
    "require_rename_cases.cljc",
    "rrb_vector_cases.cljc",
    "seq_to_map_for_destructuring_cases.cljc",
    "seque_cases.cljc",
    "set_cases.cljc",
    "shared_core_semantics_cases.cljc",
    "shell_cases.cljc",
    "source_path_cases.cljc",
    "spec_alpha_cases.cljc",
    "spec_fspec_generation_cases.cljc",
    "spec_gen_cases.cljc",
    "spec_keys_cases.cljc",
    "spec_multi_spec_cases.cljc",
    "spec_public_surface_cases.cljc",
    "spec_recursive_generation_cases.cljc",
    "spec_test_cases.cljc",
    "stacktrace_cases.cljc",
    "string_cases.cljc",
    "struct_cases.cljc",
    "suppress_read_cases.cljc",
    "tap_cases.cljc",
    "template_cases.cljc",
    "test_check_cases.cljc",
    "test_runner_cases.cljc",
    "testing_cases.cljc",
    "testing_reporting_cases.cljc",
    "tools_cli_cases.cljc",
    "tools_logging_cases.cljc",
    "tools_macro_cases.cljc",
    "tools_namespace_cases.cljc",
    "tools_reader_cases.cljc",
    "unresolved_vars_cases.cljc",
    "verbose_defrecords_cases.cljc",
    "version_compatibility_cases.cljc",
    "walk_cases.cljc",
    "xml_cases.cljc",
    "zip_cases.cljc",
)
DEFAULT_EXCLUDED_FIXTURE_NAMES = frozenset()
CLOJURE_VERSION = "1.12.4"
DEFAULT_CLOJURE_SDEPS = (
    f'{{:deps {{org.clojure/clojure {{:mvn/version \\"{CLOJURE_VERSION}\\"}} '
    'org.clojure/data.csv {:mvn/version \\"1.1.0\\"} '
    'org.clojure/data.xml {:mvn/version \\"0.2.0-alpha11\\"} '
    'org.clojure/data.json {:mvn/version \\"2.5.1\\"} '
    'org.clojure/data.codec {:mvn/version \\"0.1.1\\"} '
    'org.clojure/data.priority-map {:mvn/version \\"1.2.0\\"} '
    'org.clojure/core.cache {:mvn/version \\"1.1.234\\"} '
    'org.clojure/core.async {:mvn/version \\"1.9.865\\"} '
    'org.clojure/core.match {:mvn/version \\"1.1.1\\"} '
    'org.clojure/core.memoize {:mvn/version \\"1.1.266\\"} '
    'org.clojure/core.rrb-vector {:mvn/version \\"0.2.0\\"} '
    'org.clojure/java.classpath {:mvn/version \\"1.1.0\\"} '
    'org.clojure/tools.macro {:mvn/version \\"0.2.0\\"} '
    'org.clojure/tools.namespace {:mvn/version \\"1.5.0\\"} '
    'org.clojure/tools.logging {:mvn/version \\"1.3.0\\"} '
    'org.clojure/tools.reader {:mvn/version \\"1.5.2\\"} '
    'org.clojure/tools.cli {:mvn/version \\"1.4.256\\"} '
    'org.clojure/test.check {:mvn/version \\"1.1.1\\"} '
    'org.clojure/math.combinatorics {:mvn/version \\"0.3.0\\"}}}'
)


def _fixture_paths(fixtures: list[Path] | None) -> list[Path]:
    """Return explicitly selected fixtures or the complete conformance corpus."""

    if fixtures:
        return fixtures
    return [
        fixture
        for fixture in sorted(DEFAULT_FIXTURE_DIRECTORY.glob("*_cases.cljc"))
        if fixture.name not in DEFAULT_EXCLUDED_FIXTURE_NAMES
    ]


def conformance_inventory_errors(
    fixture_directory: Path = DEFAULT_FIXTURE_DIRECTORY,
) -> list[str]:
    """Return errors when checked-in conformance fixtures drift from the manifest."""

    observed = {fixture.name for fixture in fixture_directory.glob("*_cases.cljc")}
    expected = set(EXPECTED_CONFORMANCE_FIXTURE_NAMES)
    excluded = set(DEFAULT_EXCLUDED_FIXTURE_NAMES)

    errors: list[str] = []
    unexpected = sorted(observed - expected)
    missing = sorted(expected - observed)
    unknown_exclusions = sorted(excluded - expected)
    if unexpected:
        errors.append("unexpected conformance fixture(s): " + ", ".join(unexpected))
    if missing:
        errors.append("missing conformance fixture(s): " + ", ".join(missing))
    if unknown_exclusions:
        errors.append(
            "excluded conformance fixture(s) absent from manifest: "
            + ", ".join(unknown_exclusions)
        )
    return errors


def _shard_fixture_paths(
    fixtures: list[Path], *, shard_count: int, shard_index: int
) -> list[Path]:
    """Return the stable modulo-selected fixture shard."""

    if shard_count < 1:
        raise ValueError("shard_count must be greater than zero")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard_index must be between 0 and shard_count - 1")
    if shard_count == 1:
        return fixtures
    return [
        fixture
        for index, fixture in enumerate(fixtures)
        if index % shard_count == shard_index
    ]


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
        return f'clojure -Sdeps "{DEFAULT_CLOJURE_SDEPS}" -M'
    if os.name == "nt" and shutil.which("wsl"):
        return f'wsl -d Ubuntu-24.04 -- clojure -Sdeps "{DEFAULT_CLOJURE_SDEPS}" -M'
    return f'clojure -Sdeps "{DEFAULT_CLOJURE_SDEPS}" -M'


def _run(
    command_prefix: str,
    fixture_path: str,
    *,
    label: str,
    extra_env: Mapping[str, str] | None = None,
) -> list[str]:
    env = None
    if extra_env:
        env = os.environ.copy()
        env.update(extra_env)
    try:
        result = subprocess.run(
            [*shlex.split(command_prefix), fixture_path],
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


def _compare_outputs(
    clojure: list[str], basilisp: list[str], *, label: str, show_output: bool
) -> bool:
    if clojure != basilisp:
        print("Differential conformance mismatch", file=sys.stderr)
        print(label, file=sys.stderr)
        print(f"Clojure:  {clojure!r}", file=sys.stderr)
        print(f"Basilisp: {basilisp!r}", file=sys.stderr)
        return False
    if show_output:
        print("\n".join(basilisp))
    return True


def main(argv: list[str] | None = None) -> int:
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
    parser.add_argument(
        "--verify-inventory",
        action="store_true",
        help="fail if checked-in conformance fixtures differ from the manifest",
    )
    parser.add_argument(
        "--disable-basilisp-ns-cache",
        action="store_true",
        help=(
            "run Basilisp fixtures with BASILISP_DO_NOT_CACHE_NAMESPACES=true; "
            "useful for full-corpus parity proof runs which should not depend "
            "on pre-existing .lpyc state"
        ),
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=1,
        help="split the selected fixtures into this many stable modulo shards",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="run only this zero-based shard index",
    )
    parser.add_argument("--show-output", action="store_true")
    args = parser.parse_args(argv)

    if args.verify_inventory:
        errors = conformance_inventory_errors()
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        if not args.fixture:
            # A standalone inventory check is intentionally cheap; CI combines
            # this flag with sharded full-corpus execution.
            if args.shard_count == 1 and args.shard_index == 0:
                return 0

    fixtures = _fixture_paths(args.fixture)
    try:
        fixtures = _shard_fixture_paths(
            fixtures, shard_count=args.shard_count, shard_index=args.shard_index
        )
    except ValueError as exc:
        parser.error(str(exc))
    if not fixtures:
        parser.error("no conformance fixtures found")

    basilisp_env = (
        {"BASILISP_DO_NOT_CACHE_NAMESPACES": "true"}
        if args.disable_basilisp_ns_cache
        else None
    )
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
            extra_env=basilisp_env,
        )
        if not _compare_outputs(
            clojure,
            basilisp,
            label=f"fixture: {fixture}",
            show_output=args.show_output,
        ):
            return 1
        print(f"conformant fixture={fixture.name} cases={len(basilisp)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
