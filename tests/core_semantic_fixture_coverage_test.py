from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from scripts import core_semantic_fixture_coverage as coverage


def test_core_aliases_finds_clojure_and_basilisp_core_aliases():
    source = """
    (require '[clojure.core :as c])
    #?(:lpy (require '[basilisp.core :as bc]))
    ;; (require '[clojure.core :as ignored])
    "(require '[clojure.core :as ignored])"
    """

    assert coverage.core_aliases(source) == {"c", "bc"}


def test_split_command_preserves_windows_path_separators(monkeypatch):
    monkeypatch.setattr(coverage.os, "name", "nt")

    assert coverage._split_command(r".venv\Scripts\basilisp.exe run -c") == [
        r".venv\Scripts\basilisp.exe",
        "run",
        "-c",
    ]


def test_direct_core_references_counts_calls_and_qualified_references(tmp_path):
    fixture = tmp_path / "sample_cases.cljc"
    fixture.write_text(
        """
        (require '[clojure.core :as c])
        (map inc [1 2 3])
        (/ 6 3)
        (clojure.core/reduce + [1 2 3])
        (c/filter odd? [1 2 3])
        {:await clojure.core/await}
        (binding [*1 :one
                  *e error
                  *out* writer]
          [*1 *e primitives-classnames])
        default-data-readers
        ;; (future :comment)
        "(promise)"
        """,
        encoding="utf-8",
    )

    refs = coverage.direct_core_references(
        [fixture],
        {
            "*out*",
            "*1",
            "*e",
            "await",
            "default-data-readers",
            "filter",
            "future",
            "map",
            "/",
            "primitives-classnames",
            "promise",
            "reduce",
        },
    )

    assert set(refs) == {
        "*out*",
        "*1",
        "*e",
        "await",
        "default-data-readers",
        "filter",
        "map",
        "/",
        "primitives-classnames",
        "reduce",
    }
    assert refs["map"].modes_by_fixture[fixture] == frozenset({"unqualified-call"})
    assert refs["/"].modes_by_fixture[fixture] == frozenset({"unqualified-call"})
    assert refs["reduce"].modes_by_fixture[fixture] == frozenset(
        {"qualified-call", "qualified-reference"}
    )
    assert refs["filter"].modes_by_fixture[fixture] == frozenset(
        {"alias-call", "alias-reference"}
    )
    assert refs["await"].modes_by_fixture[fixture] == frozenset({"qualified-reference"})
    assert refs["*out*"].modes_by_fixture[fixture] == frozenset(
        {"unqualified-reference"}
    )
    assert refs["*1"].modes_by_fixture[fixture] == frozenset({"unqualified-reference"})
    assert refs["*e"].modes_by_fixture[fixture] == frozenset({"unqualified-reference"})
    assert refs["primitives-classnames"].modes_by_fixture[fixture] == frozenset(
        {"unqualified-reference"}
    )
    assert refs["default-data-readers"].modes_by_fixture[fixture] == frozenset(
        {"unqualified-reference"}
    )


def test_coverage_rows_classify_surface_and_semantic_statuses(tmp_path):
    fixture = tmp_path / "sample_cases.cljc"
    reference = coverage.CoreReference(
        "shared-covered", {fixture: frozenset({"unqualified-call"})}
    )

    rows = {
        row.symbol: row
        for row in coverage.coverage_rows(
            {"shared-covered", "shared-uncovered", "missing"},
            {"shared-covered", "shared-uncovered", "extension"},
            {"shared-covered": reference},
        )
    }

    assert rows["shared-covered"].status == "shared"
    assert rows["shared-covered"].coverage_status == "covered"
    assert rows["shared-uncovered"].coverage_status == "uncovered"
    assert rows["missing"].status == "missing-in-basilisp"
    assert rows["missing"].coverage_status == "surface-gap"
    assert rows["extension"].status == "basilisp-extension"
    assert rows["extension"].coverage_status == "extension"


def test_main_min_coverage_rejects_uncovered_shared_core_var(
    monkeypatch, tmp_path, capsys
):
    fixture = tmp_path / "sample_cases.cljc"
    fixture.write_text("(ns sample)", encoding="utf-8")

    monkeypatch.setattr(
        coverage, "_live_clojure_publics", lambda _command: {"covered", "gap"}
    )
    monkeypatch.setattr(
        coverage, "_live_basilisp_publics", lambda _command: {"covered", "gap"}
    )
    monkeypatch.setattr(
        coverage,
        "direct_core_references",
        lambda _fixtures, _shared_publics: {
            "covered": coverage.CoreReference(
                "covered", {fixture: frozenset({"unqualified-call"})}
            )
        },
    )

    assert 1 == coverage.main(
        [
            "--fixture",
            str(fixture),
            "--basilisp-command",
            "unused",
            "--min-coverage",
            "100",
        ]
    )
    assert "clojure.core direct coverage 50.0% < 100.0%" in capsys.readouterr().err


def test_main_min_coverage_accepts_fully_covered_shared_core_vars(
    monkeypatch, tmp_path
):
    fixture = tmp_path / "sample_cases.cljc"
    fixture.write_text("(ns sample)", encoding="utf-8")

    publics = {"covered-a", "covered-b"}
    monkeypatch.setattr(coverage, "_live_clojure_publics", lambda _command: publics)
    monkeypatch.setattr(coverage, "_live_basilisp_publics", lambda _command: publics)
    monkeypatch.setattr(
        coverage,
        "direct_core_references",
        lambda _fixtures, _shared_publics: {
            symbol: coverage.CoreReference(
                symbol, {fixture: frozenset({"unqualified-call"})}
            )
            for symbol in publics
        },
    )

    assert 0 == coverage.main(
        [
            "--fixture",
            str(fixture),
            "--basilisp-command",
            "unused",
            "--min-coverage",
            "100",
        ]
    )


@given(
    symbols=st.sets(
        st.from_regex(r"[a-z][a-z0-9-]{0,8}[!?]?", fullmatch=True),
        min_size=1,
        max_size=12,
    )
)
def test_coverage_rows_never_marks_unreferenced_shared_symbols_covered(symbols):
    ordered = sorted(symbols)
    referenced = set(ordered[::2])
    references = {
        symbol: coverage.CoreReference(
            symbol, {Path(f"{symbol}.cljc"): frozenset({"unqualified-call"})}
        )
        for symbol in referenced
    }

    rows = coverage.coverage_rows(set(symbols), set(symbols), references)

    covered = {row.symbol for row in rows if row.coverage_status == "covered"}
    assert covered == referenced
