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
        "clojure.core.specs.alpha",
        "clojure.uuid",
    }.issubset(surface_namespaces)


def test_jvm_and_ui_omissions_have_explicit_reasons():
    omitted = [
        classification
        for classification in inventory.CLASSIFICATIONS
        if classification.status.endswith("omitted")
    ]

    assert omitted
    assert all(not classification.basilisp_ns for classification in omitted)
    assert all(classification.reason for classification in omitted)
    assert {
        "clojure.java.browse",
        "clojure.java.javadoc",
        "clojure.test.junit",
    }.issubset({classification.clojure_ns for classification in omitted})


def test_clojure_verification_skips_non_requireable_resources():
    verified = set(inventory.clojure_require_verified_namespaces())

    assert "clojure.string" in verified
    assert "clojure.java.basis" in verified
    assert "clojure.core-deftype" not in verified
    assert "clojure.pprint.cl-format" not in verified
    assert "clojure.parallel" not in verified


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
