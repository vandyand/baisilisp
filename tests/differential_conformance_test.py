from pathlib import Path
from subprocess import CompletedProcess

import pytest
from hypothesis import given
from hypothesis import strategies as st

import scripts.differential_conformance as conformance
from scripts.differential_conformance import (
    _fixture_argument,
    _fixture_paths,
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


def test_fixture_paths_preserves_explicit_selection():
    fixture = Path("specific_cases.cljc")

    assert _fixture_paths([fixture]) == [fixture]


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
