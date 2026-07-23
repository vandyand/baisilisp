import re

from hypothesis import given
from hypothesis import strategies as st

from scripts import standard_namespace_surface_matrix as matrix


def test_namespace_pairs_are_sorted_unique_and_non_core():
    clojure_namespaces = [pair.clojure_ns for pair in matrix.STANDARD_NAMESPACE_PAIRS]
    basilisp_namespaces = [pair.basilisp_ns for pair in matrix.STANDARD_NAMESPACE_PAIRS]

    assert sorted(clojure_namespaces) == clojure_namespaces
    assert len(set(clojure_namespaces)) == len(clojure_namespaces)
    assert len(set(basilisp_namespaces)) == len(basilisp_namespaces)
    assert "clojure.core" not in clojure_namespaces
    assert all(ns.startswith("clojure.") for ns in clojure_namespaces)
    assert all(ns.startswith("basilisp.") for ns in basilisp_namespaces)
    assert {
        "clojure.core.server",
        "clojure.reflect",
        "clojure.stacktrace",
    }.issubset(clojure_namespaces)


def test_default_deps_cover_audited_external_libraries():
    deps = matrix.DEFAULT_CLOJURE_SDEPS

    assert "org.clojure/math.combinatorics" in deps
    assert "org.clojure/tools.cli" in deps
    assert "org.clojure/tools.reader" in deps
    assert "org.clojure/data.priority-map" in deps


def test_tools_logging_generated_proxy_var_is_classified_missing():
    rows = list(
        matrix._rows(
            matrix.NamespacePair(
                "clojure.tools.logging",
                "basilisp.tools.logging",
                allowed_missing=(matrix.TOOLS_LOGGING_PROXY_VAR,),
            ),
            {
                "debug",
                "clojure.tools.logging.proxy$java.io.ByteArrayOutputStream$ff19274a",
            },
            {"debug"},
        )
    )
    statuses = {row["symbol"]: row["status"] for row in rows}

    assert "shared" == statuses["debug"]
    assert (
        "classified-missing-in-basilisp"
        == statuses[
            "clojure.tools.logging.proxy$java.io.ByteArrayOutputStream$ff19274a"
        ]
    )


def test_jvm_reflect_public_vars_are_classified_missing():
    rows = list(
        matrix._rows(
            matrix.NamespacePair(
                "clojure.reflect",
                "basilisp.reflect",
                allowed_missing=(matrix.JVM_REFLECT_VAR,),
            ),
            {"reflect", "->Method", "resolve-class"},
            {"reflect", "PythonReflector"},
        )
    )
    statuses = {row["symbol"]: row["status"] for row in rows}

    assert "shared" == statuses["reflect"]
    assert "classified-missing-in-basilisp" == statuses["->Method"]
    assert "classified-missing-in-basilisp" == statuses["resolve-class"]
    assert "basilisp-extension" == statuses["PythonReflector"]


@given(
    shared=st.sets(st.from_regex(r"[a-z][a-z0-9-]{0,8}", fullmatch=True), max_size=8),
    missing=st.sets(st.from_regex(r"m[a-z0-9-]{0,8}", fullmatch=True), max_size=4),
    extensions=st.sets(st.from_regex(r"x[a-z0-9-]{0,8}", fullmatch=True), max_size=4),
)
def test_generated_surface_rows_classify_partition(shared, missing, extensions):
    missing = missing - shared
    extensions = extensions - shared - missing
    pair = matrix.NamespacePair("clojure.sample", "basilisp.sample")
    rows = matrix.rows_for_publics(
        [pair],
        {pair.clojure_ns: shared | missing},
        {pair.basilisp_ns: shared | extensions},
    )

    statuses = {row["symbol"]: row["status"] for row in rows}

    assert all(statuses[symbol] == "shared" for symbol in shared)
    assert all(statuses[symbol] == "missing-in-basilisp" for symbol in missing)
    assert all(statuses[symbol] == "basilisp-extension" for symbol in extensions)
    assert matrix.has_unclassified_missing(rows) is bool(missing)


def test_generated_surface_rows_ignore_classified_missing_symbols():
    pair = matrix.NamespacePair(
        "clojure.sample",
        "basilisp.sample",
        allowed_missing=(re.compile(r"^generated\$[0-9]+$"),),
    )
    rows = matrix.rows_for_publics(
        [pair],
        {pair.clojure_ns: {"same", "generated$123"}},
        {pair.basilisp_ns: {"same"}},
    )

    assert not matrix.has_unclassified_missing(rows)
    assert {row["symbol"]: row["status"] for row in rows} == {
        "generated$123": "classified-missing-in-basilisp",
        "same": "shared",
    }


def test_publics_expr_requires_each_namespace_and_prints_publics():
    expr = matrix._publics_expr(["clojure.string", "clojure.set"])

    assert '"clojure.string"' in expr
    assert '"clojure.set"' in expr
    assert "(require ns-sym)" in expr
    assert "(ns-publics ns-sym)" in expr
