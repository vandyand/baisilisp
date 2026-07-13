from pathlib import Path

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
