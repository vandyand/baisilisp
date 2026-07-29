from types import SimpleNamespace

from hypothesis import given
from hypothesis import strategies as st

from scripts import standard_namespace_inventory as inventory
from scripts import standard_namespace_surface_matrix as matrix


def test_bundled_namespace_inventory_is_sorted_unique_and_complete():
    namespaces = inventory.BUNDLED_CLOJURE_NAMESPACES
    classified = inventory.classification_by_namespace()

    assert tuple(sorted(namespaces)) == namespaces
    assert len(set(namespaces)) == len(namespaces)
    assert len(set(classified)) == len(inventory.CLASSIFICATIONS)
    assert set(namespaces) == set(classified)
    assert not inventory.inventory_errors()


def test_ported_non_core_namespaces_are_surface_audited():
    surface_namespaces = {pair.clojure_ns for pair in matrix.STANDARD_NAMESPACE_PAIRS}

    assert not inventory.ported_without_surface_audit()
    assert {
        "clojure.main",
        "clojure.core.specs.alpha",
        "clojure.inspector",
        "clojure.java.basis",
        "clojure.java.basis.impl",
        "clojure.java.browse",
        "clojure.java.browse-ui",
        "clojure.java.javadoc",
        "clojure.repl.deps",
        "clojure.test.junit",
        "clojure.tools.deps.interop",
        "clojure.uuid",
    }.issubset(surface_namespaces)


def test_no_ordinary_requireable_namespace_omissions_remain():
    omitted = [
        classification
        for classification in inventory.CLASSIFICATIONS
        if classification.status.endswith("omitted")
    ]
    omitted_by_namespace = {
        classification.clojure_ns: classification.status for classification in omitted
    }

    assert omitted
    assert all(not classification.basilisp_ns for classification in omitted)
    assert all(classification.reason for classification in omitted)
    assert set(omitted_by_namespace.values()) <= {"source-resource-omitted"}
    assert omitted_by_namespace == {
        "clojure.core-deftype": "source-resource-omitted",
        "clojure.core-print": "source-resource-omitted",
        "clojure.core-proxy": "source-resource-omitted",
        "clojure.genclass": "source-resource-omitted",
        "clojure.gvec": "source-resource-omitted",
        "clojure.pprint.cl-format": "source-resource-omitted",
        "clojure.pprint.column-writer": "source-resource-omitted",
        "clojure.pprint.dispatch": "source-resource-omitted",
        "clojure.pprint.pprint-base": "source-resource-omitted",
        "clojure.pprint.pretty-writer": "source-resource-omitted",
        "clojure.pprint.print-table": "source-resource-omitted",
        "clojure.pprint.utilities": "source-resource-omitted",
        "clojure.reflect.java": "source-resource-omitted",
    }
    assert set(inventory.SOURCE_RESOURCE_OMISSIONS) == set(omitted_by_namespace)


def test_source_resource_omission_mappings_pin_exact_owner_namespaces():
    assert inventory.SOURCE_RESOURCE_OMISSIONS["clojure.core-print"] == (
        "clojure/core_print.clj",
        "clojure.core",
    )
    assert inventory.SOURCE_RESOURCE_OMISSIONS["clojure.pprint.cl-format"] == (
        "clojure/pprint/cl_format.clj",
        "clojure.pprint",
    )
    assert inventory.SOURCE_RESOURCE_OMISSIONS["clojure.reflect.java"] == (
        "clojure/reflect/java.clj",
        "clojure.reflect",
    )


def test_source_resource_omission_probe_expression_covers_all_mappings():
    expr = inventory._source_resource_omission_expr()

    for namespace, (resource, owner) in inventory.SOURCE_RESOURCE_OMISSIONS.items():
        assert f'"{namespace}" "{resource}" "{owner}"' in expr
    assert "(in-ns '" in expr
    assert "(find-ns ns-sym)" in expr


def test_runtime_resource_discovery_expression_reads_active_clojure_jar():
    expr = inventory._clojure_runtime_resources_expr()

    assert '"clojure/core.clj"' in expr
    assert ".getJarFile" in expr
    assert '(.startsWith name "clojure/")' in expr
    assert '(.endsWith name ".clj")' in expr
    assert '(.endsWith name ".cljc")' in expr


def test_resource_path_to_namespace_normalizes_clojure_resource_names():
    assert (
        inventory.resource_path_to_namespace("clojure/core_print.clj")
        == "clojure.core-print"
    )
    assert (
        inventory.resource_path_to_namespace("clojure/pprint/cl_format.clj")
        == "clojure.pprint.cl-format"
    )
    assert (
        inventory.resource_path_to_namespace("clojure/spec/alpha.cljc")
        == "clojure.spec.alpha"
    )


def test_runtime_resource_verifier_rejects_unclassified_discovery(monkeypatch):
    def run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout='["clojure/core.clj" "clojure/new_runtime_ns.clj"]',
        )

    monkeypatch.setattr(inventory.subprocess, "run", run)

    errors = inventory.verify_discovered_runtime_resources(["clojure", "-e"])

    assert errors == [
        "discovered Clojure runtime resource namespaces missing inventory "
        "classification: clojure.new-runtime-ns"
    ]


@given(
    namespace=st.from_regex(
        r"clojure\.[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){0,3}",
        fullmatch=True,
    )
)
def test_generated_discovered_runtime_resource_gap_is_reported(namespace):
    if namespace in inventory.classification_by_namespace():
        return

    resource = namespace.replace(".", "/").replace("-", "_") + ".clj"

    assert inventory.runtime_resource_inventory_errors({namespace: resource}) == [
        "discovered Clojure runtime resource namespaces missing inventory "
        f"classification: {namespace}"
    ]


def test_runtime_resource_inventory_rejects_known_resource_drift():
    errors = inventory.runtime_resource_inventory_errors(
        {
            "clojure.core-print": "clojure/core_print_v2.clj",
            "clojure.parallel": "clojure/parallel_v2.clj",
        }
    )

    assert errors == [
        "clojure.core-print discovered resource mismatch: expected "
        "clojure/core_print.clj, got clojure/core_print_v2.clj",
        "clojure.parallel discovered legacy resource mismatch: expected "
        "clojure/parallel.clj, got clojure/parallel_v2.clj",
    ]


def test_runtime_resource_discovery_rejects_namespace_collisions(monkeypatch):
    monkeypatch.setattr(
        inventory,
        "_discover_clojure_runtime_resources",
        lambda _command: ("clojure/foo_bar.clj", "clojure/foo-bar.clj"),
    )

    errors = inventory.verify_discovered_runtime_resources(["clojure", "-e"])

    assert errors == [
        "multiple resources map to clojure.foo-bar: "
        "clojure/foo_bar.clj, clojure/foo-bar.clj"
    ]


def test_runtime_resource_verifier_accepts_classified_discovery(monkeypatch):
    def run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout='["clojure/core.clj" "clojure/pprint/cl_format.clj"]',
        )

    monkeypatch.setattr(inventory.subprocess, "run", run)

    assert inventory.verify_discovered_runtime_resources(["clojure", "-e"]) == []


def test_source_resource_omission_verifier_rejects_bad_probe_rows(monkeypatch):
    def run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout="\n".join(
                [
                    '[clojure.core-print :ok "clojure/core_print.clj" false true false true nil nil]',
                    '[clojure.genclass :ok "clojure/genclass.clj" true false false true nil nil]',
                    '[clojure.gvec :ok "clojure/gvec.clj" true true true true nil nil]',
                    '[clojure.reflect.java :ok "clojure/reflect/java.clj" true true false false "Error" "boom"]',
                ]
            ),
        )

    monkeypatch.setattr(inventory.subprocess, "run", run)

    errors = inventory.verify_source_resource_omissions(["clojure", "-e"])

    assert any("clojure.core-print source resource missing" in e for e in errors)
    assert any(
        "clojure.genclass source does not declare expected owner" in e for e in errors
    )
    assert any("clojure.gvec unexpectedly created a namespace" in e for e in errors)
    assert any(
        "clojure.reflect.java source resource failed to require" in e for e in errors
    )
    assert any("did not report" in e for e in errors)


def test_source_resource_omission_verifier_accepts_complete_good_probe(monkeypatch):
    def run(*_args, **_kwargs):
        rows = [
            (f'[{namespace} :ok "{resource}" ' "true true false true nil nil]")
            for namespace, (resource, _owner) in sorted(
                inventory.SOURCE_RESOURCE_OMISSIONS.items()
            )
        ]
        return SimpleNamespace(returncode=0, stderr="", stdout="\n".join(rows))

    monkeypatch.setattr(inventory.subprocess, "run", run)

    assert inventory.verify_source_resource_omissions(["clojure", "-e"]) == []


def test_legacy_parallel_is_source_audited_but_not_jvm_require_verified():
    classification = inventory.classification_by_namespace()["clojure.parallel"]

    assert classification.status == "legacy-source-audited"
    assert classification.basilisp_ns == "basilisp.parallel"
    assert "clojure.parallel" not in inventory.clojure_require_verified_namespaces()
    assert inventory.LEGACY_SOURCE_RESOURCES["clojure.parallel"] == (
        "clojure/parallel.clj"
    )


def test_legacy_source_public_parser_ignores_private_defs():
    source = """
(defn- op [f] f)
(defn par
  ([coll] coll)
  ([coll & ops] coll))
(defn pvec [pa] pa)
(defn- pa-to-vec [pa] pa)
(defn pfilter-dupes [coll] coll)
"""

    assert inventory.legacy_source_public_names(source) == (
        "par",
        "pfilter-dupes",
        "pvec",
    )


def test_clojure_verification_skips_non_requireable_resources():
    verified = set(inventory.clojure_require_verified_namespaces())

    assert "clojure.string" in verified
    assert "clojure.main" in verified
    assert "clojure.inspector" in verified
    assert "clojure.java.browse" in verified
    assert "clojure.java.javadoc" in verified
    assert "clojure.test.junit" in verified
    assert "clojure.java.basis" in verified
    assert "clojure.repl.deps" in verified
    assert "clojure.tools.deps.interop" in verified
    assert "clojure.core-deftype" not in verified
    assert "clojure.pprint.cl-format" not in verified
    assert "clojure.parallel" not in verified


def test_basilisp_verification_includes_runtime_compatibility_namespaces():
    verified = set(inventory.basilisp_require_verified_namespaces())

    assert "clojure.string" in verified
    assert "clojure.inspector" in verified
    assert "clojure.parallel" in verified
    assert "clojure.repl.deps" in verified
    assert "clojure.core-deftype" not in verified
    assert "clojure.pprint.cl-format" not in verified
    assert "clojure.reflect.java" not in verified


@given(
    namespace=st.from_regex(
        r"clojure\.[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){0,3}",
        fullmatch=True,
    )
)
def test_generated_unclassified_namespace_is_reported(namespace):
    if namespace in inventory.classification_by_namespace():
        return

    original_namespaces = inventory.BUNDLED_CLOJURE_NAMESPACES
    try:
        inventory.BUNDLED_CLOJURE_NAMESPACES = tuple(
            sorted((*original_namespaces, namespace))
        )
        assert namespace in inventory.unclassified_namespaces()
        assert any(namespace in error for error in inventory.inventory_errors())
    finally:
        inventory.BUNDLED_CLOJURE_NAMESPACES = original_namespaces


def test_inventory_rows_are_csv_ready_and_reasoned():
    rows = list(inventory.rows())

    assert len(rows) == len(inventory.BUNDLED_CLOJURE_NAMESPACES)
    assert all(
        set(row) == {"clojure_namespace", "status", "basilisp_namespace", "reason"}
        for row in rows
    )
    assert all(row["reason"] for row in rows)
