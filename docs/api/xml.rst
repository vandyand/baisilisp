basilisp.xml
============

``basilisp.xml`` provides a deliberately bounded, data-oriented XML subset.
``parse`` produces immutable ``xml/element`` struct maps with ``:tag``,
``:attrs``, and ``:content`` slots; ``emit-element`` and ``emit`` serialize
those maps. Tags and attribute names are unqualified ASCII keywords, and content
is ordered strings and child element maps. The standard ``tag``, ``attrs``, and
``content`` accessors work on values built from ``xml/element``.

The adapter rejects namespace-qualified and non-ASCII XML names, DTDs, and
entity declarations. It retains no comments or processing instructions, and it
does not promise prefix, namespace, byte, or streaming round trips. Parsing text
is capped at 4 MiB by default; pass ``:max-chars`` to choose a smaller or larger
positive bound.

The historical ``clojure.xml`` SAX public names are present for compatibility.
``sax-parser`` returns a Python SAX parser, ``disable-external-entities`` applies
supported Python SAX safety flags, and both ``startparse-sax`` and
``startparse-sax-safe`` preserve Basilisp's DTD/entity rejection boundary.

.. autonamespace:: basilisp.xml
   :members:
   :undoc-members:
