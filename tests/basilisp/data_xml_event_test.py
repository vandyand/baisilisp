from collections import deque
from random import Random

import pytest

from basilisp import data_xml as xml
from basilisp.lang import keyword as kw


class FragmentReader:
    """A deliberately short-reading text stream for incremental-parser tests."""

    def __init__(self, *fragments: str):
        self.fragments = deque(fragments)
        self.read_calls = 0

    def read(self, size: int) -> str:
        assert size == 8192
        self.read_calls += 1
        return self.fragments.popleft() if self.fragments else ""


def test_event_seq_consumes_only_the_input_needed_for_each_event():
    reader = FragmentReader("<root>", "alpha", "<child/>", "</root>", "<ignored/>")
    events = xml.event_seq(reader)

    root = next(events)
    assert isinstance(root, xml.StartElementEvent)
    assert root.tag == kw.keyword("root")
    assert reader.read_calls == 2

    assert next(events) == xml.CharsEvent("alpha")
    assert reader.read_calls == 2
    assert next(events) == xml.EmptyElementEvent(
        kw.keyword("child"), xml.lmap.EMPTY, xml.lmap.EMPTY
    )
    assert reader.read_calls == 3
    assert next(events) is xml.end_element_event
    assert reader.read_calls == 4
    assert list(reader.fragments) == ["<ignored/>"]


def test_event_seq_rejects_unsafe_declarations_split_between_reads():
    reader = FragmentReader(
        "<!DOC", "TYPE root [<!ENT", "ITY bomb 'x'>]><root>&bomb;</root>"
    )

    with pytest.raises(ValueError, match="DTD and entity declarations"):
        list(xml.event_seq(reader))


def test_event_seq_enforces_maximum_across_short_reads():
    reader = FragmentReader("<root>", "12345", "</root>")

    with pytest.raises(ValueError, match="max-chars"):
        list(xml.event_seq(reader, {kw.keyword("max-chars"): 10}))


def test_event_seq_preserves_namespace_qualified_tags_and_attributes():
    events = list(
        xml.event_seq("<r:root xmlns:r='urn:root' xmlns:a='urn:attr' a:id='7'/>")
    )
    root = events[0]

    assert isinstance(root, xml.EmptyElementEvent)
    assert xml.qname_uri(root.tag) == "urn:root"
    assert xml.qname_local(root.tag) == "root"
    assert root.attrs[xml.qname("urn:attr", "id")] == "7"


def test_event_exit_is_specific_to_the_canonical_singleton():
    assert xml.event_exit(xml.end_element_event)
    assert not xml.event_exit(xml.EndElementEvent())


class CountingContents:
    def __init__(self, *values):
        self.values = deque(values)
        self.next_calls = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.next_calls += 1
        if not self.values:
            raise StopIteration
        return self.values.popleft()


def test_flatten_elements_is_lazy_through_element_content():
    contents = CountingContents("first", "second", "third")
    source = xml.lmap.map(
        {
            kw.keyword("tag"): kw.keyword("root"),
            kw.keyword("content"): contents,
        }
    )
    events = xml.flatten_elements([source])

    assert next(events) == xml.StartElementEvent(
        kw.keyword("root"), xml.lmap.EMPTY, xml.lmap.EMPTY
    )
    assert contents.next_calls == 1
    assert next(events) == xml.CharsEvent("first")
    assert contents.next_calls == 1
    assert next(events) == xml.CharsEvent("second")
    assert contents.next_calls == 2


def test_event_tree_handles_deep_input_without_python_recursion():
    depth = 5000
    start = xml.StartElementEvent(kw.keyword("node"), xml.lmap.EMPTY, xml.lmap.EMPTY)
    root = xml.event_tree([start] * depth + [xml.end_element_event] * depth)
    tree = root

    observed_depth = 0
    while tree.get(kw.keyword("content")):
        observed_depth += 1
        tree = tree[kw.keyword("content")][0]
    assert observed_depth == depth - 1
    assert tree[kw.keyword("tag")] == kw.keyword("node")

    flattened = list(xml.flatten_elements([root]))
    assert len(flattened) == depth * 2 - 1
    assert isinstance(flattened[0], xml.StartElementEvent)
    assert isinstance(flattened[depth - 1], xml.EmptyElementEvent)
    assert flattened[-1] is xml.end_element_event


def test_event_tree_rejects_malformed_boundaries_and_accepts_leaf_nodes():
    start = xml.StartElementEvent(kw.keyword("root"), xml.lmap.EMPTY, xml.lmap.EMPTY)
    with pytest.raises(ValueError, match="unmatched end"):
        xml.event_tree([xml.end_element_event])
    with pytest.raises(ValueError, match="before its element was closed"):
        xml.event_tree([start])
    with pytest.raises(ValueError, match="flatten-elements"):
        list(xml.flatten_elements([{kw.keyword("not-a-tag"): True}]))
    assert xml.event_tree([xml.CharsEvent("leaf")]) == "leaf"


def test_seeded_nested_tree_fuzz_roundtrips_all_event_variants():
    random = Random(20260728)

    def node(depth: int):
        tag = kw.keyword(f"node-{depth}-{random.randrange(20)}")
        children = []
        for _ in range(random.randrange(5)):
            choice = random.randrange(4)
            if depth and choice == 0:
                children.append(node(depth - 1))
            elif choice == 1:
                children.append(xml.CData(f"cdata<{random.randrange(1000)}"))
            elif choice == 2:
                children.append(xml.Comment(f"comment-{random.randrange(1000)}"))
            else:
                children.append(str(random.randrange(1000)))
        return xml.element(
            tag, {kw.keyword("id"): str(random.randrange(1000))}, children
        )

    for _ in range(400):
        source = node(5)
        assert xml.event_tree(xml.flatten_elements([source])) == source
