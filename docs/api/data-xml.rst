basilisp.data.xml
=================

``basilisp.data.xml`` provides the portable tree and event-level
``clojure.data.xml`` API through the standard ``clojure.data.xml`` import
path. ``parse``/``parse-str`` return immutable ``{:tag :attrs :content}``
element maps, including URI-qualified keyword QNames. ``emit``/``emit-str``
and their indented counterparts write compatible XML to Python text writers.

DTD and entity declarations are rejected before parsing, and input is bounded
by ``:max-chars`` (4 MiB by default). ``event-seq`` is a lazy SAX-backed event
stream: it consumes a text reader incrementally and emits the familiar start,
empty, character, CDATA, comment, and end-element records without realizing a
tree. ``event-node`` and ``event-element`` convert individual records back
into the tree representation. ``flatten-elements`` lazily turns trees or XML
leaf nodes into events, while ``event-tree`` rebuilds the first complete tree
without recursive Python traversal. The same transformation functions are
available from the standard ``clojure.data.xml.tree`` import path.

Python's SAX API does not provide JVM StAX location metadata or the lexical
namespace-prefix environment, so event ``location-info`` is ``nil`` and
``nss`` is an empty map. Processing instructions are safely skipped because
``clojure.data.xml`` has no corresponding event record.

.. autonamespace:: basilisp.data.xml
   :members:
   :undoc-members:
