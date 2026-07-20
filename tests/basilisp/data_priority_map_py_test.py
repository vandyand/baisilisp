import random

from basilisp.lang.priority_map import (
    PersistentPriorityMap,
    priority_map,
    priority_map_by,
    priority_map_keyfn,
    rsubseq,
    subseq,
)


def test_priority_map_preserves_map_contract_and_priority_queue_order():
    original = priority_map("a", 2, "b", 1, "c", 3)
    changed = original.assoc("a", 0)

    assert isinstance(original, PersistentPriorityMap)
    assert dict(original.items()) == {"a": 2, "b": 1, "c": 3}
    assert list(original.items()) == [("b", 1), ("a", 2), ("c", 3)]
    assert tuple(original.peek()) == ("b", 1)
    assert list(original.pop().items()) == [("a", 2), ("c", 3)]
    assert list(changed.items()) == [("a", 0), ("b", 1), ("c", 3)]
    assert original["a"] == 2


def test_comparator_keyfn_and_bounded_ordering():
    descending = priority_map_by(
        lambda left, right: left > right, "a", 1, "b", 3, "c", 2
    )
    keyed = priority_map_keyfn(
        lambda value: value[0], "a", (2, "apple"), "b", (1, "banana")
    )

    assert list(descending.items()) == [("b", 3), ("c", 2), ("a", 1)]
    assert list(keyed.items()) == [("b", (1, "banana")), ("a", (2, "apple"))]
    natural = priority_map("a", 2, "b", 1, "c", 3)
    assert [
        tuple(entry) for entry in subseq(natural, lambda left, right: left < right, 3)
    ] == [
        ("b", 1),
        ("a", 2),
    ]
    assert [
        tuple(entry) for entry in rsubseq(natural, lambda left, right: left >= right, 2)
    ] == [
        ("c", 3),
        ("a", 2),
    ]


def test_random_reassignment_and_pop_model_preserves_persistence():
    source = random.Random(89431)
    model: dict[int, int] = {}
    queue = priority_map()
    snapshots = []

    for _ in range(2500):
        item = source.randrange(150)
        if source.random() < 0.7:
            priority = source.randrange(-100, 101)
            snapshots.append((queue, dict(model)))
            model[item] = priority
            queue = queue.assoc(item, priority)
        elif item in model:
            snapshots.append((queue, dict(model)))
            del model[item]
            queue = queue.dissoc(item)

        expected_priorities = sorted(model.values())
        assert dict(queue.items()) == model
        assert [priority for _, priority in queue.items()] == expected_priorities
        if expected_priorities:
            assert queue.peek().value == expected_priorities[0]

    for snapshot, expected in snapshots[::97]:
        assert dict(snapshot.items()) == expected
