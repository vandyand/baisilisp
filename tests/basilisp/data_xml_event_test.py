from collections import deque

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


def test_event_exit_accepts_equivalent_record_instances():
    assert xml.event_exit(xml.end_element_event)
    assert xml.event_exit(xml.EndElementEvent())
