from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import vector as vec
from tests.basilisp.helpers import CompileFn

BOUNDARIES = (
    0,
    1,
    31,
    32,
    33,
    63,
    64,
    65,
    1_023,
    1_024,
    1_025,
    1_055,
    1_056,
    1_057,
    32_767,
    32_768,
    32_769,
)


@pytest.fixture
def test_ns() -> str:
    return "vector-tree-test"


@pytest.fixture
def compiler_file_path() -> str:
    return "<vector tree test>"


@pytest.mark.parametrize("count", BOUNDARIES)
def test_vector_tree_crosses_every_branch_and_tail_boundary(count: int):
    values = list(range(count))
    vector = vec.vector(values)

    assert list(vector) == values
    assert len(vector) == count
    assert vector._count == count  # pylint: disable=protected-access
    assert vector._shift in (5, 10, 15)
    assert len(vector._tail) == (  # pylint: disable=protected-access
        count - ((count - 1) // 32 * 32) if count else 0
    )

    if count:
        assert vector[0] == 0
        assert vector[-1] == count - 1
        assert vector.nth(-1) == count - 1
        assert list(vector.pop()) == values[:-1]
        assert list(vector.assoc(count, count)) == values + [count]
        assert list(vector.assoc(-1, "tail")) == values[:-1] + ["tail"]


def test_vector_tree_path_copies_only_the_changed_branch_and_never_mutates_source():
    source = vec.vector(range(1_057))
    changed_tree = source.assoc(0, "root-change")
    changed_tail = source.assoc(-1, "tail-change")
    appended = source.cons("append")
    overflowed = source.cons(*range(32))

    assert source[0] == 0
    assert source[-1] == 1_056
    assert changed_tree[0] == "root-change"
    assert changed_tree._root is not source._root  # pylint: disable=protected-access
    assert changed_tree._tail is source._tail  # pylint: disable=protected-access
    assert changed_tail._root is source._root  # pylint: disable=protected-access
    assert changed_tail._tail is not source._tail  # pylint: disable=protected-access
    assert appended._root is source._root  # pylint: disable=protected-access
    assert appended._tail is not source._tail  # pylint: disable=protected-access
    assert overflowed._root is not source._root  # pylint: disable=protected-access
    assert appended[:-1] == source


def test_vector_nodes_are_immutable_snapshots_and_empty_node_is_canonical():
    supplied = [None] * 32
    node = vec.vec_node("edit", supplied)
    supplied[0] = "mutated-after-construction"

    assert node.edit == "edit"
    assert node.arr[0] is None
    assert len(node.arr) == 32
    assert len(vec.EMPTY_NODE.arr) == 32
    assert all(item is None for item in vec.EMPTY_NODE.arr)
    assert vec.EMPTY._root is vec.EMPTY_NODE  # pylint: disable=protected-access


def test_raw_vec_components_and_vecseq_validate_real_tree_structure():
    source = vec.vector(range(64))
    metadata = lmap.map({"source": "raw-components"})
    reconstructed = vec.vec_from_components(
        object(),
        source._count,  # pylint: disable=protected-access
        source._shift,  # pylint: disable=protected-access
        source._root,  # pylint: disable=protected-access
        source._tail,  # pylint: disable=protected-access
        metadata,
    )

    assert reconstructed == source
    assert reconstructed.meta == metadata
    assert reconstructed._root is source._root  # pylint: disable=protected-access
    sequence = vec.vec_seq(
        None,
        reconstructed,
        reconstructed._array_for(32),  # pylint: disable=protected-access
        32,
        7,
        lmap.map({"sequence": True}),
    )
    assert list(sequence) == list(range(39, 64))
    assert sequence.meta == lmap.map({"sequence": True})
    assert sequence.with_meta(metadata).meta == metadata

    with pytest.raises(ValueError, match="tail has"):
        vec.vec_from_components(
            None,
            source._count,  # pylint: disable=protected-access
            source._shift,  # pylint: disable=protected-access
            source._root,  # pylint: disable=protected-access
            (),
            None,
        )
    with pytest.raises(ValueError, match="does not match"):
        vec.vec_seq(None, source, tuple(range(32)), 32, 0, None)
    with pytest.raises(IndexError, match="chunk boundary"):
        vec.vec_seq(
            None, source, source._array_for(0), 1, 0, None
        )  # pylint: disable=protected-access


def test_transient_vector_isolated_across_boundaries_and_after_persistence():
    source = vec.vector(range(1_057))
    transient = source.to_transient()
    transient.assoc_transient(0, "changed", len(source), "appended", len(source) + 1)
    transient.cons_transient("last")
    persisted = transient.to_persistent()

    assert source[0] == 0
    assert len(source) == 1_057
    assert persisted[0] == "changed"
    assert list(persisted[-3:]) == ["appended", None, "last"]
    assert len(persisted) == len(source) + 3


@given(
    initial=st.lists(st.integers(), max_size=160),
    operations=st.lists(
        st.tuples(st.sampled_from(("append", "assoc", "pop")), st.integers()),
        max_size=240,
    ),
)
@settings(max_examples=150, deadline=None)
def test_vector_tree_fuzzes_persistent_operations_against_python_list(
    initial: list[int], operations: list[tuple[str, int]]
):
    vector = vec.vector(initial)
    model: list[Any] = list(initial)

    for operation, value in operations:
        before = vector
        if operation == "append":
            vector = vector.cons(value)
            model.append(value)
        elif operation == "assoc":
            index = value % (len(model) + 1)
            vector = vector.assoc(index, value)
            if index == len(model):
                model.append(value)
            else:
                model[index] = value
        elif model:
            vector = vector.pop()
            model.pop()

        assert list(vector) == model
        assert list(before) != model or before == vector


def test_vector_tree_is_safe_for_concurrent_readers_and_independent_writers():
    source = vec.vector(range(32_769))

    def derive(index: int):
        changed = source.assoc(index % len(source), -index).cons(index)
        return changed[0], changed[-2], changed[-1], len(changed)

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(derive, range(2_048)))

    assert list(source[:4]) == [0, 1, 2, 3]
    assert source[-1] == 32_768
    assert all(length == len(source) + 1 for _, _, _, length in results)
    assert all(last == index for index, (_, _, last, _) in enumerate(results))


def test_core_vec_constructors_are_public_and_preserve_python_native_contract(
    lcompile: CompileFn,
):
    assert (
        lcompile("""
        (let [node (->VecNode nil (concat [nil] (repeat 31 nil)))
              value (->Vec nil 3 5 EMPTY-NODE [1 2 3] {:meta :vector})
              sequence (->VecSeq nil value [1 2 3] 0 1 {:meta :sequence})]
          {:node-empty? (nil? (first (.-arr node)))
           :vector value
           :vector-meta (meta value)
           :sequence (vec sequence)
           :sequence-meta (meta sequence)})
        """)
        == lmap.map(
            {
                kw.keyword("node-empty?"): True,
                kw.keyword("vector"): vec.v(1, 2, 3),
                kw.keyword("vector-meta"): lmap.map(
                    {kw.keyword("meta"): kw.keyword("vector")}
                ),
                kw.keyword("sequence"): vec.v(2, 3),
                kw.keyword("sequence-meta"): lmap.map(
                    {kw.keyword("meta"): kw.keyword("sequence")}
                ),
            }
        )
    )
