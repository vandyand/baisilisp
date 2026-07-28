from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from scripts import semantic_fixture_coverage as coverage
from scripts import standard_namespace_surface_matrix as surface


def test_aliases_by_namespace_finds_clojure_and_basilisp_aliases():
    pairs = (
        surface.NamespacePair("clojure.edn", "basilisp.edn"),
        surface.NamespacePair("clojure.spec.alpha", "basilisp.spec.alpha"),
    )
    source = """
    #?(:clj (require '[clojure.edn :as edn])
       :lpy (require '[basilisp.edn :as edn]))
    (require '[clojure.spec.alpha :as s])
    """

    assert coverage.aliases_by_namespace(source, pairs) == {
        "basilisp.edn": {"edn"},
        "basilisp.spec.alpha": {"s"},
    }


def test_direct_references_are_grouped_by_audited_basilisp_namespace(tmp_path):
    fixture = tmp_path / "sample_cases.cljc"
    fixture.write_text(
        """
        (require '[clojure.edn :as edn]
                 '[clojure.spec.alpha :as s])
        (edn/read-string "{:a 1}")
        (edn/read {:eof :done} reader)
        (s/conform int? 1)
        'edn/read-string
        """,
        encoding="utf-8",
    )
    pairs = (
        surface.NamespacePair("clojure.edn", "basilisp.edn"),
        surface.NamespacePair("clojure.spec.alpha", "basilisp.spec.alpha"),
    )

    refs = coverage.direct_references_by_namespace([fixture], pairs)

    assert set(refs) == {"basilisp.edn", "basilisp.spec.alpha"}
    assert set(refs["basilisp.edn"]) == {"read", "read-string"}
    assert refs["basilisp.edn"]["read-string"] == {fixture}
    assert set(refs["basilisp.spec.alpha"]) == {"conform"}


def test_coverage_rows_split_covered_and_uncovered_symbols(tmp_path):
    fixture = tmp_path / "edn_cases.cljc"
    pair = surface.NamespacePair("clojure.edn", "basilisp.edn")
    references = {"basilisp.edn": {"read-string": {fixture}, "extension": {fixture}}}

    rows = coverage.coverage_rows(
        [pair],
        {"basilisp.edn": {"read", "read-string"}},
        references,
    )

    assert rows[0].covered_symbols == ("read-string",)
    assert rows[0].uncovered_symbols == ("read",)
    assert rows[0].fixture_count == 1
    assert rows[0].reference_count == 1
    assert rows[0].coverage_percent == 50.0


@given(
    symbols=st.sets(
        st.from_regex(r"[a-z][a-z0-9-]{0,8}[!?]?", fullmatch=True),
        min_size=1,
        max_size=12,
    )
)
def test_coverage_rows_never_counts_non_public_references(symbols):
    pair = surface.NamespacePair("clojure.sample", "basilisp.sample")
    ordered = sorted(symbols)
    publics = set(ordered[::2])
    references = {
        "basilisp.sample": {symbol: {Path("fixture.cljc")} for symbol in symbols}
    }

    rows = coverage.coverage_rows([pair], {"basilisp.sample": publics}, references)

    assert set(rows[0].covered_symbols) == publics
    assert not (set(rows[0].uncovered_symbols) & set(rows[0].covered_symbols))
