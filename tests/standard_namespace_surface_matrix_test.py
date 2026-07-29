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
        "clojure.inspector",
        "clojure.java.basis",
        "clojure.java.basis.impl",
        "clojure.java.browse",
        "clojure.java.browse-ui",
        "clojure.java.classpath",
        "clojure.java.javadoc",
        "clojure.main",
        "clojure.reflect",
        "clojure.repl.deps",
        "clojure.stacktrace",
        "clojure.test.check",
        "clojure.test.check.clojure-test",
        "clojure.test.check.clojure-test.assertions",
        "clojure.test.check.clojure-test.assertions.cljs",
        "clojure.test.check.generators",
        "clojure.test.check.impl",
        "clojure.test.check.properties",
        "clojure.test.check.random",
        "clojure.test.check.results",
        "clojure.test.check.rose-tree",
        "clojure.test.junit",
        "clojure.tools.deps.interop",
        "clojure.tools.logging.readable",
        "clojure.tools.reader.default-data-readers",
        "clojure.tools.reader.edn",
        "clojure.tools.reader.impl.commons",
        "clojure.tools.reader.impl.errors",
        "clojure.tools.reader.impl.inspect",
        "clojure.tools.reader.impl.utils",
        "clojure.tools.namespace.move",
        "clojure.tools.namespace.repl",
    }.issubset(clojure_namespaces)


def test_default_deps_cover_audited_external_libraries():
    deps = matrix.DEFAULT_CLOJURE_SDEPS

    assert "org.clojure/clojure" in deps
    assert matrix.CLOJURE_VERSION in deps
    assert "org.clojure/java.classpath" in deps
    assert "org.clojure/math.combinatorics" in deps
    assert "org.clojure/tools.cli" in deps
    assert "org.clojure/tools.reader" in deps
    assert "org.clojure/data.priority-map" in deps


def test_tools_logging_generated_proxy_var_is_non_portable_artifact():
    rows = list(
        matrix._rows(
            matrix.NamespacePair(
                "clojure.tools.logging",
                "basilisp.tools.logging",
                non_portable_artifacts=(matrix.TOOLS_LOGGING_PROXY_VAR,),
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
        "non-portable-artifact"
        == statuses[
            "clojure.tools.logging.proxy$java.io.ByteArrayOutputStream$ff19274a"
        ]
    )


def test_tools_reader_generated_proxy_var_is_non_portable_artifact():
    rows = list(
        matrix._rows(
            matrix.NamespacePair(
                "clojure.tools.reader.default-data-readers",
                "basilisp.tools.reader.default-data-readers",
                non_portable_artifacts=(matrix.TOOLS_READER_THREAD_LOCAL_PROXY_VAR,),
            ),
            {
                "default-uuid-reader",
                "clojure.tools.reader.default_data_readers.proxy$java.lang.ThreadLocal$ff19274a",
            },
            {"default-uuid-reader"},
        )
    )
    statuses = {row["symbol"]: row["status"] for row in rows}

    assert "shared" == statuses["default-uuid-reader"]
    assert (
        "non-portable-artifact"
        == statuses[
            "clojure.tools.reader.default_data_readers.proxy$java.lang.ThreadLocal$ff19274a"
        ]
    )


def test_test_check_random_generated_proxy_var_is_non_portable_artifact():
    rows = list(
        matrix._rows(
            matrix.NamespacePair(
                "clojure.test.check.random",
                "basilisp.test.check.random",
                non_portable_artifacts=(
                    matrix.TEST_CHECK_RANDOM_THREAD_LOCAL_PROXY_VAR,
                ),
            ),
            {
                "make-random",
                "clojure.test.check.random.proxy$java.lang.ThreadLocal$ff19274a",
            },
            {"make-random"},
        )
    )
    statuses = {row["symbol"]: row["status"] for row in rows}

    assert "shared" == statuses["make-random"]
    assert (
        "non-portable-artifact"
        == statuses["clojure.test.check.random.proxy$java.lang.ThreadLocal$ff19274a"]
    )


def test_reflect_public_vars_are_shared_when_implemented():
    rows = list(
        matrix._rows(
            matrix.NamespacePair("clojure.reflect", "basilisp.reflect"),
            {"reflect", "->Method", "resolve-class"},
            {"reflect", "->Method", "resolve-class", "PythonReflector"},
        )
    )
    statuses = {row["symbol"]: row["status"] for row in rows}

    assert "shared" == statuses["reflect"]
    assert "shared" == statuses["->Method"]
    assert "shared" == statuses["resolve-class"]
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


def test_generated_surface_rows_ignore_non_portable_artifacts():
    pair = matrix.NamespacePair(
        "clojure.sample",
        "basilisp.sample",
        non_portable_artifacts=(re.compile(r"^generated\$[0-9]+$"),),
    )
    rows = matrix.rows_for_publics(
        [pair],
        {pair.clojure_ns: {"same", "generated$123"}},
        {pair.basilisp_ns: {"same"}},
    )

    assert not matrix.has_unclassified_missing(rows)
    assert {row["symbol"]: row["status"] for row in rows} == {
        "generated$123": "non-portable-artifact",
        "same": "shared",
    }


def test_publics_expr_requires_each_namespace_and_prints_publics():
    expr = matrix._publics_expr(["clojure.string", "clojure.set"])

    assert '"clojure.string"' in expr
    assert '"clojure.set"' in expr
    assert "(require ns-sym)" in expr
    assert "(ns-publics ns-sym)" in expr
