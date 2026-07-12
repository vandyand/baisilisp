import random
from collections.abc import Callable

import pytest

from basilisp import main
from basilisp.lang import runtime
from basilisp.lang import symbol as sym
from basilisp.lang import vector as lvec


@pytest.fixture(scope="module", autouse=True)
def initialize_runtime():
    main.init()
    __import__("basilisp.zip")


def _zip_var(name: str):
    var = runtime.Var.find(sym.symbol(name, ns="basilisp.zip"))
    assert var is not None
    return var.value


def _tree(rng: random.Random, depth: int, next_leaf: list[int]):
    if depth == 0 or rng.random() < 0.45:
        leaf = next_leaf[0]
        next_leaf[0] += 1
        return leaf
    return lvec.vector(
        _tree(rng, depth - 1, next_leaf) for _ in range(rng.randrange(0, 5))
    )


def _preorder(node) -> list:
    if isinstance(node, lvec.PersistentVector):
        return [node, *[value for child in node for value in _preorder(child)]]
    return [node]


def _map_leaves(node, f: Callable[[int], int]):
    if isinstance(node, lvec.PersistentVector):
        return lvec.vector(_map_leaves(child, f) for child in node)
    return f(node)


def _remove_leaves(node, should_remove: Callable[[int], bool]):
    if isinstance(node, lvec.PersistentVector):
        return lvec.vector(
            _remove_leaves(child, should_remove)
            for child in node
            if isinstance(child, lvec.PersistentVector) or not should_remove(child)
        )
    return node


def _last_loc(loc, next_fn, end_fn):
    while not end_fn(next_fn(loc)):
        loc = next_fn(loc)
    return loc


def test_randomized_traversal_edit_and_removal_invariants():
    rng = random.Random(0x21F00D)
    vector_zip = _zip_var("vector-zip")
    node = _zip_var("node")
    branch = _zip_var("branch?")
    next_fn = _zip_var("next")
    prev = _zip_var("prev")
    end = _zip_var("end?")
    root = _zip_var("root")
    replace = _zip_var("replace")
    remove = _zip_var("remove")

    for _ in range(150):
        tree = _tree(rng, 5, [0])
        if not isinstance(tree, lvec.PersistentVector):
            tree = lvec.vector([tree])

        loc = vector_zip(tree)
        visited = []
        while not end(loc):
            visited.append(node(loc))
            loc = next_fn(loc)
        assert visited == _preorder(tree)
        assert root(loc) == tree

        last = _last_loc(vector_zip(tree), next_fn, end)
        reverse_visited = []
        while last is not None:
            reverse_visited.append(node(last))
            last = prev(last)
        assert reverse_visited == list(reversed(visited))

        loc = vector_zip(tree)
        while not end(loc):
            if not branch(loc):
                loc = replace(loc, node(loc) + 10_000)
            loc = next_fn(loc)
        assert root(loc) == _map_leaves(tree, lambda value: value + 10_000)

        should_remove = lambda value: value % 3 == 0
        loc = vector_zip(tree)
        while not end(loc):
            if not branch(loc) and should_remove(node(loc)):
                loc = remove(loc)
            loc = next_fn(loc)
        assert root(loc) == _remove_leaves(tree, should_remove)


def test_deep_tree_navigation_does_not_lose_edits():
    vector_zip = _zip_var("vector-zip")
    node = _zip_var("node")
    down = _zip_var("down")
    up = _zip_var("up")
    replace = _zip_var("replace")
    root = _zip_var("root")

    tree = 0
    for _ in range(128):
        tree = lvec.vector([tree])

    loc = vector_zip(tree)
    for _ in range(128):
        loc = down(loc)
        assert loc is not None
    loc = replace(loc, 1)
    for _ in range(128):
        loc = up(loc)
        assert loc is not None
    assert node(loc) != tree
    assert root(loc) == _map_leaves(tree, lambda _: 1)
