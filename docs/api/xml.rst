basilisp.xml
============

``basilisp.xml`` provides a deliberately bounded, data-oriented XML subset.
``parse`` produces immutable element maps shaped as ``{:tag :attrs :content}``;
``emit-element`` and ``emit`` serialize those maps. Tags and attribute names are
unqualified ASCII keywords, and content is ordered strings and child maps.

The adapter rejects namespace-qualified and non-ASCII XML names, DTDs, and
entity declarations. It retains no comments or processing instructions, and it
does not promise prefix, namespace, byte, or streaming round trips. Parsing text
is capped at 4 MiB by default; pass ``:max-chars`` to choose a smaller or larger
positive bound.

.. autonamespace:: basilisp.xml
   :members:
   :undoc-members:
