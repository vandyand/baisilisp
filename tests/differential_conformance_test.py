from pathlib import Path
from subprocess import CompletedProcess

import pytest
from hypothesis import given
from hypothesis import strategies as st

import scripts.differential_conformance as conformance
from scripts.differential_conformance import (
    _fixture_argument,
    _fixture_paths,
    _shard_fixture_paths,
    _normalize_edn,
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
