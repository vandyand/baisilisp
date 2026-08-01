from pathlib import Path
from shutil import copytree
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given
from hypothesis import strategies as st

import scripts.library_acceptance as acceptance
from scripts.library_acceptance import (
    _shard_library_roots,
    acceptance_manifest,
    verify_manifest,
)


def test_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "portable_library"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert '"reader_features": [' in manifest
    assert "clojure.string -> basilisp.string" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_upstream_acceptance_manifest_is_portable_and_checked_in():
    library_root = (
        Path(__file__).parent / "acceptance" / "upstream" / "cognitect-anomalies"
    )
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.spec.alpha -> basilisp.spec.alpha" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_tools_cli_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "tools-cli"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.tools.cli -> basilisp.tools.cli" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )
    production_source = (
        Path(__file__).parents[1] / "src" / "basilisp" / "tools" / "cli.lpy"
    )
    acceptance_source = (
        library_root / "port" / "src" / "basilisp" / "tools" / "cli.cljc"
    )
    assert production_source.read_text(encoding="utf-8") == acceptance_source.read_text(
        encoding="utf-8"
    )


def test_tools_namespace_acceptance_manifest_is_host_adapted_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "tools-namespace"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "jvm-only"' in manifest
    assert "clojure.tools.namespace -> basilisp.tools.namespace" in manifest
    assert "org.clojure/tools.namespace 1.5.0 Maven artifact" in manifest
    assert "java-interop" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_math_combinatorics_acceptance_manifest_is_portable_and_checked_in():
    library_root = (
        Path(__file__).parent / "acceptance" / "upstream" / "math-combinatorics"
    )
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.math.combinatorics -> basilisp.math.combinatorics" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )
    production_source = (
        Path(__file__).parents[1] / "src" / "basilisp" / "math" / "combinatorics.lpy"
    )
    acceptance_source = (
        library_root / "port" / "src" / "basilisp" / "math" / "combinatorics.cljc"
    )
    assert production_source.read_text(encoding="utf-8") == acceptance_source.read_text(
        encoding="utf-8"
    )


def test_medley_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "medley"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "JVM collection dispatch -> Basilisp collection protocols" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_algo_generic_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "algo-generic"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.algo.generic -> basilisp.algo.generic" in manifest
    assert "JVM Number dispatch -> Basilisp numeric host-type dispatch" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_algo_monads_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "algo-monads"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.algo.monads -> basilisp.algo.monads" in manifest
    assert "clojure.tools.macro -> basilisp.tools.macro" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_core_unify_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "core-unify"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.core.unify -> basilisp.core.unify" in manifest
    assert (
        "JVM IllegalStateException occurs-check failures -> Python RuntimeError"
        in manifest
    )
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_core_cache_memoize_acceptance_manifest_is_portable_and_checked_in():
    library_root = (
        Path(__file__).parent / "acceptance" / "upstream" / "core-cache-memoize"
    )
    manifest = acceptance_manifest(library_root)

    assert '"classification": "jvm-only"' in manifest
    assert "clojure.core.cache -> basilisp.core.cache" in manifest
    assert "clojure.core.memoize -> basilisp.core.memoize" in manifest
    assert (
        "JVM SoftReference cache operations remain excluded from the portable acceptance contract"
        in manifest
    )
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_core_async_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "core-async"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.core.async -> basilisp.core.async" in manifest
    assert (
        "Clojure IOC go state machine -> Basilisp asyncio coroutine-backed go subset"
        in manifest
    )
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_data_csv_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "data-csv"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.data.csv -> basilisp.data.csv" in manifest
    assert "org.clojure/data.csv 1.1.0 Maven artifact" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_data_json_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "data-json"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.data.json -> basilisp.data.json" in manifest
    assert "org.clojure/data.json 2.5.1 Maven artifact" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_data_xml_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "data-xml"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.data.xml -> basilisp.data.xml" in manifest
    assert "org.clojure/data.xml 0.2.0-alpha11 Maven artifact" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_data_priority_map_acceptance_manifest_is_portable_and_checked_in():
    library_root = (
        Path(__file__).parent / "acceptance" / "upstream" / "data-priority-map"
    )
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.data.priority-map -> basilisp.data.priority-map" in manifest
    assert "org.clojure/data.priority-map 1.2.0 Maven artifact" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_data_codec_base64_acceptance_manifest_is_portable_and_checked_in():
    library_root = (
        Path(__file__).parent / "acceptance" / "upstream" / "data-codec-base64"
    )
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.data.codec.base64 -> basilisp.data.codec.base64" in manifest
    assert "org.clojure/data.codec 0.1.1 Maven artifact" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_tools_reader_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "tools-reader"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.tools.reader -> basilisp.tools.reader" in manifest
    assert "org.clojure/tools.reader 1.5.2 Maven artifact" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_tools_logging_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "tools-logging"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.tools.logging -> basilisp.tools.logging" in manifest
    assert "org.clojure/tools.logging 1.3.0 Maven artifact" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_test_check_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "test-check"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.test.check -> basilisp.test.check" in manifest
    assert "org.clojure/test.check 1.1.1 Maven artifact" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_core_match_acceptance_manifest_is_portable_and_checked_in():
    library_root = Path(__file__).parent / "acceptance" / "upstream" / "core-match"
    manifest = acceptance_manifest(library_root)

    assert '"classification": "portable"' in manifest
    assert "clojure.core.match -> basilisp.core.match" in manifest
    assert "org.clojure/core.match 1.1.1 Maven artifact" in manifest
    assert manifest == verify_manifest(
        library_root, library_root / "portability-manifest.json"
    )


def test_acceptance_library_roots_discovers_checked_in_libraries(tmp_path):
    first = tmp_path / "portable"
    second = tmp_path / "upstream" / "library"
    noise = tmp_path / "missing-manifest"
    for library in (first, second, noise):
        library.mkdir(parents=True)
        (library / "run.cljc").write_text("", encoding="utf-8")
    for library in (first, second):
        (library / "portability-manifest.json").write_text("{}", encoding="utf-8")

    assert acceptance.acceptance_library_roots(tmp_path) == [first, second]


def test_acceptance_library_inventory_is_sorted_unique_and_checked_in():
    expected = acceptance.EXPECTED_ACCEPTANCE_LIBRARY_ROOTS
    observed = tuple(
        acceptance._relative_acceptance_root(root)
        for root in acceptance.acceptance_library_roots()
    )

    assert tuple(sorted(expected)) == expected
    assert len(set(expected)) == len(expected)
    assert observed == expected
    assert acceptance.acceptance_inventory_errors() == []


def test_acceptance_library_inventory_reports_unexpected_and_missing_roots(tmp_path):
    expected = tmp_path / "expected"
    unexpected = tmp_path / "unexpected"
    for library in (expected, unexpected):
        library.mkdir()
        (library / "run.cljc").write_text("", encoding="utf-8")
        (library / "portability-manifest.json").write_text("{}", encoding="utf-8")

    original = acceptance.EXPECTED_ACCEPTANCE_LIBRARY_ROOTS
    try:
        acceptance.EXPECTED_ACCEPTANCE_LIBRARY_ROOTS = ("expected", "missing")
        assert acceptance.acceptance_inventory_errors(tmp_path) == [
            "unexpected acceptance library root(s): unexpected",
            "missing acceptance library root(s): missing",
        ]
    finally:
        acceptance.EXPECTED_ACCEPTANCE_LIBRARY_ROOTS = original


@given(
    unexpected=st.lists(
        st.from_regex(r"generated-[a-z0-9]{1,6}", fullmatch=True),
        min_size=1,
        max_size=5,
        unique=True,
    )
)
def test_generated_acceptance_inventory_drift_is_reported(unexpected):
    with TemporaryDirectory() as dirname:
        root = Path(dirname)
        for name in unexpected:
            library = root / name
            library.mkdir()
            (library / "run.cljc").write_text("", encoding="utf-8")
            (library / "portability-manifest.json").write_text("{}", encoding="utf-8")

        original = acceptance.EXPECTED_ACCEPTANCE_LIBRARY_ROOTS
        try:
            acceptance.EXPECTED_ACCEPTANCE_LIBRARY_ROOTS = ()
            assert acceptance.acceptance_inventory_errors(root) == [
                "unexpected acceptance library root(s): "
                + ", ".join(sorted(unexpected))
            ]
        finally:
            acceptance.EXPECTED_ACCEPTANCE_LIBRARY_ROOTS = original


def test_default_clojure_command_pins_verified_clojure_version(monkeypatch):
    monkeypatch.delenv("CLOJURE_COMMAND", raising=False)
    monkeypatch.setattr(acceptance.shutil, "which", lambda name: name == "clojure")

    command = acceptance._default_clojure_command()

    assert "clojure -Sdeps" in command
    assert "org.clojure/clojure" in command
    assert acceptance.CLOJURE_VERSION in command


def test_default_clojure_command_accepts_library_extra_deps(monkeypatch):
    monkeypatch.delenv("CLOJURE_COMMAND", raising=False)
    monkeypatch.setattr(acceptance.shutil, "which", lambda name: name == "clojure")

    command = acceptance._default_clojure_command({"org.clojure/core.async": "1.9.865"})

    assert "org.clojure/clojure" in command
    assert acceptance.CLOJURE_VERSION in command
    assert "org.clojure/core.async" in command
    assert "1.9.865" in command


def test_shard_library_roots_selects_stable_modulo_shards():
    roots = [Path(f"library-{index}") for index in range(7)]

    assert _shard_library_roots(roots, shard_count=1, shard_index=0) == roots
    assert _shard_library_roots(roots, shard_count=3, shard_index=0) == [
        Path("library-0"),
        Path("library-3"),
        Path("library-6"),
    ]
    assert _shard_library_roots(roots, shard_count=3, shard_index=1) == [
        Path("library-1"),
        Path("library-4"),
    ]
    assert _shard_library_roots(roots, shard_count=3, shard_index=2) == [
        Path("library-2"),
        Path("library-5"),
    ]


@pytest.mark.parametrize(
    "shard_count,shard_index",
    [(0, 0), (1, -1), (2, 2)],
)
def test_shard_library_roots_rejects_invalid_requests(shard_count, shard_index):
    with pytest.raises(ValueError):
        _shard_library_roots(
            [Path("library")],
            shard_count=shard_count,
            shard_index=shard_index,
        )


def test_main_all_runs_every_checked_in_library(monkeypatch, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    observed = []

    monkeypatch.setattr(acceptance, "acceptance_library_roots", lambda: [first, second])
    monkeypatch.setattr(acceptance, "acceptance_inventory_errors", lambda: [])
    monkeypatch.setattr(
        acceptance,
        "_accept_library",
        lambda library_root, manifest_path, **kwargs: observed.append(
            (library_root, manifest_path, kwargs)
        )
        or True,
    )

    assert 0 == acceptance.main(
        [
            "--all",
            "--verify-inventory",
            "--clojure-command",
            "clj",
            "--basilisp-command",
            "lpy",
        ]
    )
    assert [
        (first.resolve(), first.resolve() / "portability-manifest.json"),
        (second.resolve(), second.resolve() / "portability-manifest.json"),
    ] == [(library_root, manifest_path) for library_root, manifest_path, _ in observed]
    assert all(
        item[2]["clojure_command"] == "clj" and item[2]["basilisp_command"] == "lpy"
        for item in observed
    )
    assert all(item[2]["basilisp_env"] is None for item in observed)


def test_main_all_applies_sharding_and_basilisp_cache_disable(monkeypatch, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    third = tmp_path / "third"
    for library in (first, second, third):
        library.mkdir()
    observed = []

    monkeypatch.setattr(
        acceptance, "acceptance_library_roots", lambda: [first, second, third]
    )
    monkeypatch.setattr(acceptance, "acceptance_inventory_errors", lambda: [])
    monkeypatch.setattr(
        acceptance,
        "_accept_library",
        lambda library_root, manifest_path, **kwargs: observed.append(
            (library_root, manifest_path, kwargs)
        )
        or True,
    )

    assert 0 == acceptance.main(
        [
            "--all",
            "--verify-inventory",
            "--shard-count",
            "2",
            "--shard-index",
            "1",
            "--disable-basilisp-ns-cache",
        ]
    )

    assert [(second.resolve(), second.resolve() / "portability-manifest.json")] == [
        (library_root, manifest_path) for library_root, manifest_path, _ in observed
    ]
    assert observed[0][2]["basilisp_env"] == {
        "BASILISP_DO_NOT_CACHE_NAMESPACES": "true"
    }


def test_accept_library_adds_configured_clojure_deps(monkeypatch, tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    runner = library / "run.cljc"
    runner.write_text("(println {:ok true})", encoding="utf-8")
    (library / "acceptance.json").write_text(
        '{"clojure_deps": {"org.clojure/core.async": "1.9.865"}}',
        encoding="utf-8",
    )
    (library / "portability-manifest.json").write_text("manifest", encoding="utf-8")
    observed_commands = []

    monkeypatch.setattr(acceptance, "verify_manifest", lambda *_: "manifest")
    monkeypatch.setattr(acceptance.shutil, "which", lambda name: name == "clojure")

    def fake_run(command, runner_path, **kwargs):
        observed_commands.append((command, runner_path, kwargs))
        return ["{:ok true}"]

    monkeypatch.setattr(acceptance, "_run", fake_run)

    assert acceptance._accept_library(
        library,
        library / "portability-manifest.json",
        clojure_command=acceptance._default_clojure_command(),
        basilisp_command="basilisp run",
    )
    assert "org.clojure/core.async" in observed_commands[0][0]
    assert observed_commands[1][0] == "basilisp run"


def test_main_all_stops_on_first_acceptance_mismatch(monkeypatch, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    observed = []

    monkeypatch.setattr(acceptance, "acceptance_library_roots", lambda: [first, second])
    monkeypatch.setattr(acceptance, "acceptance_inventory_errors", lambda: [])

    def accept_library(library_root, manifest_path, **kwargs):
        observed.append(library_root)
        return False

    monkeypatch.setattr(acceptance, "_accept_library", accept_library)

    assert 1 == acceptance.main(["--all"])
    assert observed == [first.resolve()]


def test_main_all_stops_before_execution_on_inventory_drift(monkeypatch, capsys):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("acceptance execution should not run")

    monkeypatch.setattr(
        acceptance,
        "acceptance_inventory_errors",
        lambda: ["unexpected acceptance library root(s): surprise"],
    )
    monkeypatch.setattr(acceptance, "acceptance_library_roots", fail_if_called)
    monkeypatch.setattr(acceptance, "_accept_library", fail_if_called)

    assert 1 == acceptance.main(["--all", "--verify-inventory"])
    assert "unexpected acceptance library root" in capsys.readouterr().err


def test_main_verify_inventory_can_run_without_library_execution(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("acceptance execution should not run")

    monkeypatch.setattr(acceptance, "acceptance_inventory_errors", lambda: [])
    monkeypatch.setattr(acceptance, "acceptance_library_roots", fail_if_called)
    monkeypatch.setattr(acceptance, "_accept_library", fail_if_called)

    assert 0 == acceptance.main(["--verify-inventory"])


def test_main_all_rejects_explicit_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(acceptance, "acceptance_library_roots", lambda: [])

    with pytest.raises(SystemExit):
        acceptance.main(["--all", "--manifest", str(tmp_path / "manifest.json")])


def test_main_single_library_rejects_sharding(tmp_path):
    with pytest.raises(SystemExit):
        acceptance.main(["--library-root", str(tmp_path), "--shard-count", "2"])


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ("[]", "must be an object"),
        ('{"source_root": ".."}', "must stay within the library"),
        ('{"substitutions": ["valid", 1]}', "substitutions must be strings"),
        ('{"clojure_deps": ["not-a-map"]}', "clojure_deps must map"),
        ('{"clojure_deps": {"org.clojure/core.async": 1}}', "clojure_deps must map"),
        ('{"run_via_load_file": "yes"}', "run_via_load_file must be a boolean"),
    ],
)
def test_acceptance_settings_reject_invalid_configuration(tmp_path, config, message):
    (tmp_path / "acceptance.json").write_text(config, encoding="utf-8")

    with pytest.raises(RuntimeError, match=message):
        acceptance._acceptance_settings(tmp_path)


def test_verify_manifest_rejects_missing_and_tampered_artifacts(tmp_path):
    source_root = Path(__file__).parent / "acceptance" / "portable_library"
    library_root = tmp_path / "portable_library"
    copytree(source_root, library_root)
    manifest_path = library_root / "portability-manifest.json"

    manifest_path.unlink()
    with pytest.raises(RuntimeError, match="manifest is missing"):
        verify_manifest(library_root, manifest_path)

    manifest_path.write_text(acceptance_manifest(library_root), encoding="utf-8")
    source = library_root / "src" / "acceptance" / "portable_library" / "util.cljc"
    source.write_text(
        source.read_text(encoding="utf-8") + "\n;; tampered\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="manifest is stale"):
        verify_manifest(library_root, manifest_path)


def test_acceptance_run_uses_only_the_final_edn_summary(monkeypatch, tmp_path):
    runner = tmp_path / "run.cljc"
    monkeypatch.setattr(
        acceptance.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(
            args,
            0,
            stdout="Testing example\n{:pass 2 :fail 0}\n",
            stderr="",
        ),
    )

    assert [acceptance._normalize_edn("{:pass 2 :fail 0}")] == acceptance._run(
        "basilisp run", runner, label="Basilisp"
    )


def test_acceptance_run_merges_extra_environment(monkeypatch, tmp_path):
    runner = tmp_path / "run.cljc"
    seen_env = {}

    def fake_run(*args, **kwargs):
        seen_env.update(kwargs["env"])
        return CompletedProcess(args, 0, stdout="{:pass 1 :fail 0}\n", stderr="")

    monkeypatch.setenv("BASILISP_EXISTING_ENV", "preserved")
    monkeypatch.setattr(acceptance.subprocess, "run", fake_run)

    acceptance._run(
        "basilisp run",
        runner,
        label="Basilisp",
        extra_env={"BASILISP_DO_NOT_CACHE_NAMESPACES": "true"},
    )

    assert seen_env["BASILISP_EXISTING_ENV"] == "preserved"
    assert seen_env["BASILISP_DO_NOT_CACHE_NAMESPACES"] == "true"


def test_acceptance_run_can_load_entrypoint_as_code(monkeypatch, tmp_path):
    runner = tmp_path / "run.cljc"
    runner.write_text("(println {:pass 1})", encoding="utf-8")
    observed = {}

    def fake_run(args, **kwargs):
        observed["args"] = args
        return CompletedProcess(args, 0, stdout="{:pass 1}\n", stderr="")

    monkeypatch.setattr(acceptance.subprocess, "run", fake_run)

    acceptance._run(
        "uv run basilisp run",
        runner,
        label="Basilisp",
        load_via_code=True,
    )

    assert observed["args"][-2:] == [
        "-c",
        f'(load-file "{runner.resolve().as_posix()}")',
    ]


def test_acceptance_run_load_entrypoint_detects_path_qualified_basilisp(
    monkeypatch, tmp_path
):
    runner = tmp_path / "run.cljc"
    runner.write_text("(println {:pass 1})", encoding="utf-8")
    observed = {}

    def fake_run(args, **kwargs):
        observed["args"] = args
        return CompletedProcess(args, 0, stdout="{:pass 1}\n", stderr="")

    monkeypatch.setattr(acceptance.subprocess, "run", fake_run)

    acceptance._run(
        ".tox/py314/bin/basilisp run",
        runner,
        label="Basilisp",
        load_via_code=True,
    )

    assert observed["args"][-2:] == [
        "-c",
        f'(load-file "{runner.resolve().as_posix()}")',
    ]


def test_acceptance_run_load_entrypoint_uses_clojure_eval(monkeypatch, tmp_path):
    runner = tmp_path / "run.cljc"
    runner.write_text("(println {:pass 1})", encoding="utf-8")
    observed = {}

    def fake_run(args, **kwargs):
        observed["args"] = args
        return CompletedProcess(args, 0, stdout="{:pass 1}\n", stderr="")

    monkeypatch.setattr(acceptance.subprocess, "run", fake_run)

    acceptance._run(
        "clojure -M",
        runner,
        label="Clojure",
        load_via_code=True,
    )

    assert observed["args"][-2:] == [
        "-e",
        f'(load-file "{runner.resolve().as_posix()}")',
    ]


@pytest.mark.parametrize("output", ["", "Testing example\n{:pass 1} {:fail 0}\n"])
def test_acceptance_run_rejects_missing_or_malformed_final_summary(
    monkeypatch, tmp_path, output
):
    runner = tmp_path / "run.cljc"
    monkeypatch.setattr(
        acceptance.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args, 0, stdout=output, stderr=""),
    )

    with pytest.raises(RuntimeError):
        acceptance._run("basilisp run", runner, label="Basilisp")


def test_acceptance_run_surfaces_runtime_failure_stderr(monkeypatch, tmp_path):
    runner = tmp_path / "run.cljc"
    monkeypatch.setattr(
        acceptance.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(
            args, 9, stdout="", stderr="test namespace exploded"
        ),
    )

    with pytest.raises(
        RuntimeError, match="(?s)Basilisp acceptance run failed.*exploded"
    ):
        acceptance._run("basilisp run", runner, label="Basilisp")


@pytest.mark.slow
def test_checked_in_acceptance_libraries_execute_under_available_runtimes():
    try:
        result = acceptance.main(["--all"])
    except RuntimeError as exc:
        if "command is unavailable" in str(exc):
            pytest.skip(str(exc))
        raise

    assert result == 0
