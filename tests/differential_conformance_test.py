from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given
from hypothesis import strategies as st

import scripts.differential_conformance as conformance
from scripts.differential_conformance import (
    _fixture_argument,
    _fixture_paths,
    _normalize_edn,
    _shard_fixture_paths,
)


def test_normalize_edn_compares_maps_independently_of_print_order():
    assert _normalize_edn("{:case :ref :value {:a 1 :b 2}}") == _normalize_edn(
        "{:value {:b 2 :a 1} :case :ref}"
    )


def test_fixture_paths_defaults_to_the_sorted_corpus():
    fixtures = _fixture_paths(None)

    assert fixtures == sorted(fixtures)
    assert fixtures
    assert all(path.parent.name == "conformance" for path in fixtures)
    assert "prepl_cases.cljc" not in {path.name for path in fixtures}


def test_conformance_fixture_inventory_is_sorted_unique_and_checked_in():
    expected = conformance.EXPECTED_CONFORMANCE_FIXTURE_NAMES
    observed = tuple(
        sorted(
            path.name
            for path in conformance.DEFAULT_FIXTURE_DIRECTORY.glob("*_cases.cljc")
        )
    )

    assert tuple(sorted(expected)) == expected
    assert len(set(expected)) == len(expected)
    assert observed == expected
    assert set(conformance.DEFAULT_EXCLUDED_FIXTURE_NAMES) <= set(expected)
    assert conformance.conformance_inventory_errors() == []


def test_conformance_fixture_inventory_reports_unexpected_and_missing_fixtures(
    tmp_path,
):
    for name in ("expected_cases.cljc", "unexpected_cases.cljc"):
        (tmp_path / name).write_text("(ns fixture)", encoding="utf-8")

    original = conformance.EXPECTED_CONFORMANCE_FIXTURE_NAMES
    original_excluded = conformance.DEFAULT_EXCLUDED_FIXTURE_NAMES
    try:
        conformance.EXPECTED_CONFORMANCE_FIXTURE_NAMES = (
            "expected_cases.cljc",
            "missing_cases.cljc",
        )
        conformance.DEFAULT_EXCLUDED_FIXTURE_NAMES = frozenset()
        assert conformance.conformance_inventory_errors(tmp_path) == [
            "unexpected conformance fixture(s): unexpected_cases.cljc",
            "missing conformance fixture(s): missing_cases.cljc",
        ]
    finally:
        conformance.EXPECTED_CONFORMANCE_FIXTURE_NAMES = original
        conformance.DEFAULT_EXCLUDED_FIXTURE_NAMES = original_excluded


@given(
    unexpected=st.lists(
        st.from_regex(r"generated_[a-z0-9]{1,6}_cases\.cljc", fullmatch=True),
        min_size=1,
        max_size=5,
        unique=True,
    )
)
def test_generated_conformance_inventory_drift_is_reported(unexpected):
    with TemporaryDirectory() as dirname:
        root = Path(dirname)
        for name in unexpected:
            (root / name).write_text("(ns fixture)", encoding="utf-8")

        original = conformance.EXPECTED_CONFORMANCE_FIXTURE_NAMES
        original_excluded = conformance.DEFAULT_EXCLUDED_FIXTURE_NAMES
        try:
            conformance.EXPECTED_CONFORMANCE_FIXTURE_NAMES = ()
            conformance.DEFAULT_EXCLUDED_FIXTURE_NAMES = frozenset()
            assert conformance.conformance_inventory_errors(root) == [
                "unexpected conformance fixture(s): " + ", ".join(sorted(unexpected))
            ]
        finally:
            conformance.EXPECTED_CONFORMANCE_FIXTURE_NAMES = original
            conformance.DEFAULT_EXCLUDED_FIXTURE_NAMES = original_excluded


def test_fixture_paths_preserves_explicit_selection():
    fixture = Path("prepl_cases.cljc")

    assert _fixture_paths([fixture]) == [fixture]


def test_shard_fixture_paths_selects_stable_modulo_shards():
    fixtures = [Path(f"{index}_cases.cljc") for index in range(10)]

    assert _shard_fixture_paths(fixtures, shard_count=1, shard_index=0) == fixtures
    assert _shard_fixture_paths(fixtures, shard_count=3, shard_index=0) == [
        Path("0_cases.cljc"),
        Path("3_cases.cljc"),
        Path("6_cases.cljc"),
        Path("9_cases.cljc"),
    ]
    assert _shard_fixture_paths(fixtures, shard_count=3, shard_index=1) == [
        Path("1_cases.cljc"),
        Path("4_cases.cljc"),
        Path("7_cases.cljc"),
    ]
    assert _shard_fixture_paths(fixtures, shard_count=3, shard_index=2) == [
        Path("2_cases.cljc"),
        Path("5_cases.cljc"),
        Path("8_cases.cljc"),
    ]


@pytest.mark.parametrize(
    "shard_count,shard_index",
    [(0, 0), (1, -1), (2, 2)],
)
def test_shard_fixture_paths_rejects_invalid_requests(shard_count, shard_index):
    with pytest.raises(ValueError):
        _shard_fixture_paths(
            [Path("one_cases.cljc")],
            shard_count=shard_count,
            shard_index=shard_index,
        )


def test_default_deps_cover_conformance_external_libraries():
    deps = conformance.DEFAULT_CLOJURE_SDEPS

    assert "org.clojure/clojure" in deps
    assert conformance.CLOJURE_VERSION in deps
    assert "org.clojure/java.classpath" in deps
    assert "org.clojure/math.combinatorics" in deps
    assert "org.clojure/tools.cli" in deps
    assert "org.clojure/core.async" in deps
    assert "org.clojure/core.match" in deps
    assert "org.clojure/tools.logging" in deps
    assert "org.clojure/tools.reader" in deps


def test_native_fixture_argument_is_absolute(tmp_path):
    fixture = tmp_path / "fixture.cljc"

    assert _fixture_argument(fixture, "clojure -M") == str(fixture.resolve())


@given(st.dictionaries(st.sampled_from(["a", "b", "c", "d"]), st.integers()))
def test_normalize_edn_handles_random_map_print_order(values):
    forward = "{" + " ".join(f":{key} {value}" for key, value in values.items()) + "}"
    reverse = (
        "{"
        + " ".join(f":{key} {value}" for key, value in reversed(tuple(values.items())))
        + "}"
    )

    assert _normalize_edn(forward) == _normalize_edn(reverse)


@pytest.mark.parametrize("output", ["", "{:case :one} {:case :two}\n"])
def test_run_rejects_missing_or_malformed_edn_output(monkeypatch, output):
    monkeypatch.setattr(
        conformance.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args, 0, stdout=output, stderr=""),
    )

    with pytest.raises(RuntimeError):
        conformance._run("clojure -M", "fixture.cljc", label="Clojure")


def test_run_surfaces_runtime_failure_stderr(monkeypatch):
    monkeypatch.setattr(
        conformance.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(
            args, 17, stdout="", stderr="fixture exploded"
        ),
    )

    with pytest.raises(
        RuntimeError, match="(?s)Clojure fixture failed.*fixture exploded"
    ):
        conformance._run("clojure -M", "fixture.cljc", label="Clojure")


def test_run_merges_extra_environment(monkeypatch):
    seen_env = {}

    def fake_run(*args, **kwargs):
        seen_env.update(kwargs["env"])
        return CompletedProcess(args, 0, stdout="{:case :ok}\n", stderr="")

    monkeypatch.setenv("BASILISP_EXISTING_ENV", "preserved")
    monkeypatch.setattr(conformance.subprocess, "run", fake_run)

    conformance._run(
        "basilisp run",
        "fixture.cljc",
        label="Basilisp",
        extra_env={"BASILISP_DO_NOT_CACHE_NAMESPACES": "true"},
    )

    assert seen_env["BASILISP_EXISTING_ENV"] == "preserved"
    assert seen_env["BASILISP_DO_NOT_CACHE_NAMESPACES"] == "true"


def test_main_verify_inventory_can_run_without_fixture_execution(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("fixture execution should not run")

    monkeypatch.setattr(conformance, "conformance_inventory_errors", lambda: [])
    monkeypatch.setattr(conformance, "_run", fail_if_called)

    assert 0 == conformance.main(["--verify-inventory"])


def test_main_stops_before_execution_on_inventory_drift(monkeypatch, capsys):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("fixture execution should not run")

    monkeypatch.setattr(
        conformance,
        "conformance_inventory_errors",
        lambda: ["unexpected conformance fixture(s): surprise_cases.cljc"],
    )
    monkeypatch.setattr(conformance, "_run", fail_if_called)

    assert 1 == conformance.main(["--verify-inventory"])
    assert "unexpected conformance fixture" in capsys.readouterr().err
