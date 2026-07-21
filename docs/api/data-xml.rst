basilisp.data.xml
=================

``basilisp.data.xml`` provides the portable tree-level
``clojure.data.xml`` API through the standard ``clojure.data.xml`` import
path. ``parse``/``parse-str`` return immutable ``{:tag :attrs :content}``
element maps, including URI-qualified keyword QNames. ``emit``/``emit-str``
and their indented counterparts write compatible XML to Python text writers.

DTD and entity declarations are rejected before parsing, and input is bounded
by ``:max-chars`` (4 MiB by default). The JVM pull-event record and lazy
stream APIs are not exposed in this tree tranche; Python's ElementTree parser
does not offer their equivalent event/location contract without a separate
streaming backend.

.. autonamespace:: basilisp.data.xml
   :members:
   :undoc-members:
