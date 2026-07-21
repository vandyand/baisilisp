"""Namespace-aware, safe XML tree support for ``clojure.data.xml``."""

from __future__ import annotations

import io
import re
import uuid
import xml.etree.ElementTree as etree
import xml.sax
import xml.sax.handler
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import vector as vec

DEFAULT_MAX_CHARS = 4 * 1024 * 1024
_UNSAFE_DECLARATION = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CData:
    content: str


@dataclass(frozen=True)
class Comment:
    content: str


@dataclass(frozen=True)
class StartElementEvent:
    tag: kw.Keyword
    attrs: lmap.PersistentMap
    nss: lmap.PersistentMap
    location_info: Any = None


@dataclass(frozen=True)
class EmptyElementEvent:
    tag: kw.Keyword
    attrs: lmap.PersistentMap
    nss: lmap.PersistentMap
    location_info: Any = None


@dataclass(frozen=True)
class CharsEvent:
    str: str


@dataclass(frozen=True)
class CDataEvent:
    str: str


@dataclass(frozen=True)
class CommentEvent:
    str: str


@dataclass(frozen=True)
class QNameEvent:
    qn: kw.Keyword


@dataclass(frozen=True)
class EndElementEvent:
    pass


end_element_event = EndElementEvent()


def encode_uri(value: Any) -> str:
    return quote(str(value), safe="")


def decode_uri(value: Any) -> str:
    return unquote(str(value))


def qname(uri: Any = "", local: Any | None = None, _prefix: Any = None) -> kw.Keyword:
    if local is None:
        local, uri = uri, ""
    uri = str(uri or "")
    return kw.keyword(str(local), ns=f"xmlns.{encode_uri(uri)}" if uri else None)


def qname_uri(name: Any) -> str:
    if not isinstance(name, kw.Keyword):
        raise TypeError("XML QName must be a keyword")
    if name.ns is None:
        return ""
    if name.ns == "xmlns":
        return "http://www.w3.org/2000/xmlns/"
    if name.ns == "xml":
        return "http://www.w3.org/XML/1998/namespace"
    if not name.ns.startswith("xmlns."):
        raise ValueError("keyword namespace is not an XML URI encoding")
    return decode_uri(name.ns[len("xmlns.") :])


def qname_local(name: Any) -> str:
    if not isinstance(name, kw.Keyword):
        raise TypeError("XML QName must be a keyword")
    return name.name


def _etree_name(name: Any) -> str:
    uri = qname_uri(name)
    return f"{{{uri}}}{qname_local(name)}" if uri else qname_local(name)


def _qname(name: str) -> kw.Keyword:
    if name.startswith("{"):
        uri, local = name[1:].split("}", 1)
        return qname(uri, local)
    return qname(name)


def _safe_source(source: Any, max_chars: int) -> str:
    if hasattr(source, "read"):
        source = source.read(max_chars + 1)
    if isinstance(source, bytes):
        source = source.decode("utf-8")
    if not isinstance(source, str):
        raise TypeError("XML source must be text, UTF-8 bytes, or a readable stream")
    if len(source) > max_chars:
        raise ValueError("XML input exceeds :max-chars")
    if _UNSAFE_DECLARATION.search(source):
        raise ValueError("XML DTD and entity declarations are not permitted")
    return source


def _element_from_etree(
    element: etree.Element, include_comments: bool
) -> lmap.PersistentMap:
    content: list[Any] = []
    if element.text:
        content.append(element.text)
    for child in element:
        if child.tag is etree.Comment:
            if include_comments:
                content.append(Comment(child.text or ""))
        else:
            content.append(_element_from_etree(child, include_comments))
        if child.tail:
            content.append(child.tail)
    data: dict[Any, Any] = {kw.keyword("tag"): _qname(element.tag)}
    if element.attrib:
        data[kw.keyword("attrs")] = lmap.map(
            {_qname(k): v for k, v in element.attrib.items()}
        )
    if content:
        data[kw.keyword("content")] = vec.vector(content)
    return lmap.map(data)


def parse(source: Any, options: Mapping[Any, Any] | None = None) -> lmap.PersistentMap:
    options = {} if options is None else options
    max_chars = options.get(kw.keyword("max-chars"), DEFAULT_MAX_CHARS)
    if not isinstance(max_chars, int) or max_chars <= 0:
        raise ValueError(":max-chars must be a positive integer")
    include = options.get(
        kw.keyword("include-node?"), {kw.keyword("element"), kw.keyword("characters")}
    )
    include_comments = kw.keyword("comment") in include
    parser = etree.XMLParser(target=etree.TreeBuilder(insert_comments=include_comments))
    root = etree.fromstring(_safe_source(source, max_chars), parser=parser)
    return _element_from_etree(root, include_comments)


class _EventHandler(xml.sax.handler.ContentHandler):
    def __init__(self, include_comments: bool) -> None:
        super().__init__()
        self.events: deque[Any] = deque()
        self._pending: list[tuple[kw.Keyword, lmap.PersistentMap]] = []
        self._include_comments = include_comments
        self._in_cdata = False

    def _flush_pending(self) -> None:
        if self._pending:
            tag, attrs = self._pending.pop()
            self.events.append(StartElementEvent(tag, attrs, lmap.EMPTY))

    def startElementNS(self, name, _qname, attrs):  # noqa: N802
        self._flush_pending()
        uri, local = name
        converted = {
            qname(attr_uri or "", attr_local): value
            for (attr_uri, attr_local), value in attrs.items()
        }
        self._pending.append((qname(uri or "", local), lmap.map(converted)))

    def endElementNS(self, _name, _qname):  # noqa: N802
        if self._pending:
            tag, attrs = self._pending.pop()
            self.events.append(EmptyElementEvent(tag, attrs, lmap.EMPTY))
        else:
            self.events.append(end_element_event)

    def characters(self, content: str) -> None:
        if not content:
            return
        self._flush_pending()
        event_type = CDataEvent if self._in_cdata else CharsEvent
        if self.events and isinstance(self.events[-1], event_type):
            previous = self.events[-1]
            self.events[-1] = event_type(previous.str + content)
        else:
            self.events.append(event_type(content))

    def startCDATA(self):  # noqa: N802
        self._flush_pending()
        self._in_cdata = True

    def endCDATA(self):  # noqa: N802
        self._in_cdata = False

    def comment(self, content: str) -> None:
        # A comment makes ``<tag>...</tag>`` non-empty even when the caller
        # elects not to receive CommentEvents.  Preserve that distinction from
        # the lexical ``<tag/>`` form before conditionally dropping it.
        self._flush_pending()
        if self._include_comments:
            self.events.append(CommentEvent(content))

    def processingInstruction(self, _target, _data):  # noqa: N802
        # data.xml has no processing-instruction event record, but it still
        # prevents its containing element from being an empty-element event.
        self._flush_pending()

    def startDTD(self, _name, _public_id, _system_id):  # noqa: N802
        raise ValueError("XML DTD and entity declarations are not permitted")

    def endDTD(self):  # noqa: N802
        pass

    def startEntity(self, _name):  # noqa: N802
        pass

    def endEntity(self, _name):  # noqa: N802
        pass


def _event_chunks(source: Any, max_chars: int):
    if isinstance(source, bytes):
        source = source.decode("utf-8")
    if isinstance(source, str):
        reader = io.StringIO(source)
    elif hasattr(source, "read"):
        reader = source
    else:
        raise TypeError("XML source must be text, UTF-8 bytes, or a readable stream")
    total = 0
    # Keep an unfinished ``<!   `` prefix across reads.  A fixed-size overlap
    # would let a declaration with unusually long whitespace evade the source
    # guard when its keyword begins in a later chunk.
    declaration_prefix = ""
    while True:
        chunk = reader.read(8192)
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        if not chunk:
            return
        total += len(chunk)
        if total > max_chars:
            raise ValueError("XML input exceeds :max-chars")
        candidate = declaration_prefix + chunk
        if _UNSAFE_DECLARATION.search(candidate):
            raise ValueError("XML DTD and entity declarations are not permitted")
        marker = candidate.rfind("<!")
        suffix = candidate[marker:] if marker >= 0 else ""
        declaration_prefix = suffix if re.fullmatch(r"<!\s*", suffix) else ""
        yield chunk


def event_seq(source: Any, options: Mapping[Any, Any] | None = None):
    """Yield a secure incremental sequence of data.xml-compatible events."""
    options = {} if options is None else options
    max_chars = options.get(kw.keyword("max-chars"), DEFAULT_MAX_CHARS)
    if not isinstance(max_chars, int) or max_chars <= 0:
        raise ValueError(":max-chars must be a positive integer")
    include = options.get(
        kw.keyword("include-node?"), {kw.keyword("element"), kw.keyword("characters")}
    )
    handler = _EventHandler(kw.keyword("comment") in include)
    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_namespaces, True)
    for feature in (
        xml.sax.handler.feature_external_ges,
        xml.sax.handler.feature_external_pes,
    ):
        try:
            parser.setFeature(feature, False)
        except xml.sax.SAXNotSupportedException:
            pass
    parser.setContentHandler(handler)
    try:
        parser.setProperty(xml.sax.handler.property_lexical_handler, handler)
    except (xml.sax.SAXNotRecognizedException, xml.sax.SAXNotSupportedException):
        pass
    for chunk in _event_chunks(source, max_chars):
        parser.feed(chunk)
        while handler.events:
            yield handler.events.popleft()
    parser.close()
    while handler.events:
        yield handler.events.popleft()


def event_exit(value: Any) -> bool:
    """Return true for an end-element event."""
    return isinstance(value, EndElementEvent)


def event_node(value: Any) -> Any:
    """Convert a leaf event to its data.xml node representation."""
    if isinstance(value, CharsEvent):
        return value.str
    if isinstance(value, CDataEvent):
        return CData(value.str)
    if isinstance(value, CommentEvent):
        return Comment(value.str)
    raise ValueError("event-node requires a character, CDATA, or comment event")


def event_element(value: Any, content: Sequence[Any] | None = None):
    """Build a tree element from a start or empty-element event."""
    if not isinstance(value, (StartElementEvent, EmptyElementEvent)):
        raise ValueError("event-element requires a start or empty-element event")
    return element(value.tag, value.attrs, content)


def element(
    tag: Any,
    attrs: Mapping[Any, Any] | None = None,
    content: Sequence[Any] | None = None,
):
    data: dict[Any, Any] = {kw.keyword("tag"): tag}
    if attrs:
        data[kw.keyword("attrs")] = lmap.map(dict(attrs))
    if content:
        data[kw.keyword("content")] = vec.vector(x for x in content if x is not None)
    return lmap.map(data)


def element_p(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get(kw.keyword("tag")) is not None


def _append(parent: etree.Element, value: Any, cdata_tokens: dict[str, str]) -> None:
    if isinstance(value, CData):
        token = f"__BASILISP_CDATA_{uuid.uuid4().hex}__"
        cdata_tokens[token] = value.content.replace("]]>", "]]><![CDATA[>")
        value = token
    if isinstance(value, Comment):
        child = etree.Comment(value.content)
        parent.append(child)
        return
    if isinstance(value, Mapping) and element_p(value):
        child = _to_etree(value, cdata_tokens)
        parent.append(child)
        return
    text = str(value)
    if len(parent):
        parent[-1].tail = (parent[-1].tail or "") + text
    else:
        parent.text = (parent.text or "") + text


def _to_etree(
    value: Mapping[Any, Any], cdata_tokens: dict[str, str] | None = None
) -> etree.Element:
    cdata_tokens = {} if cdata_tokens is None else cdata_tokens
    tag = value.get(kw.keyword("tag"))
    if tag is None:
        raise ValueError("element requires a :tag")
    attrs = value.get(kw.keyword("attrs"), {})
    node = etree.Element(
        _etree_name(tag), {_etree_name(k): str(v) for k, v in attrs.items()}
    )
    for child in value.get(kw.keyword("content"), ()):
        _append(node, child, cdata_tokens)
    return node


def _replace_cdata_tokens(text: str, cdata_tokens: Mapping[str, str]) -> str:
    for token, content in cdata_tokens.items():
        text = text.replace(token, f"<![CDATA[{content}]]>")
    return text


def emit_str(value: Any, options: Mapping[Any, Any] | None = None) -> str:
    options = {} if options is None else options
    encoding = options.get(kw.keyword("encoding"), "UTF-8")
    declaration = options.get(kw.keyword("declaration"), True)
    cdata_tokens: dict[str, str] = {}
    document = _replace_cdata_tokens(
        etree.tostring(
            _to_etree(value, cdata_tokens),
            encoding="unicode",
            short_empty_elements=True,
        ),
        cdata_tokens,
    )
    doctype = options.get(kw.keyword("doctype"))
    prefix = f"<?xml version='1.0' encoding='{encoding}'?>\n" if declaration else ""
    if doctype:
        prefix += f"<!DOCTYPE {doctype}>\n"
    return prefix + document


def emit(value: Any, writer: Any, options: Mapping[Any, Any] | None = None) -> None:
    writer.write(emit_str(value, options))


def indent_str(value: Any, options: Mapping[Any, Any] | None = None) -> str:
    cdata_tokens: dict[str, str] = {}
    root = _to_etree(value, cdata_tokens)
    etree.indent(root, space="  ")
    options = dict(options or {})
    encoding = options.get(kw.keyword("encoding"), "UTF-8")
    declaration = options.get(kw.keyword("declaration"), True)
    text = _replace_cdata_tokens(
        etree.tostring(root, encoding="unicode", short_empty_elements=True),
        cdata_tokens,
    )
    return (
        f"<?xml version='1.0' encoding='{encoding}'?>\n" if declaration else ""
    ) + text


def indent(value: Any, writer: Any, options: Mapping[Any, Any] | None = None) -> None:
    writer.write(indent_str(value, options))
