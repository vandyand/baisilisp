basilisp.tools.namespace
========================

``basilisp.tools.namespace`` provides the portable
``clojure.tools.namespace`` development workflow: source discovery, namespace
declaration parsing, dependency tracking, and REPL refresh.

Use :lpy:ns:`basilisp.tools.namespace.repl` for ``refresh`` and
``refresh-all``. By default it scans Basilisp ``.lpy`` and ``.cljc`` files with
the ``:lpy`` reader feature; use the exported ``find/clj`` or ``find/cljs``
platforms when scanning those source trees. Refresh explicitly discards
Basilisp bytecode cache entries for changed namespaces, including same-size
edits within a filesystem timestamp tick.

The source-moving refactoring API from upstream is deliberately not exposed:
it is labelled alpha upstream, is destructive, and has no safe cross-platform
text-rewrite contract. The discovery and reload APIs are non-destructive apart
from their normal in-process namespace reload effects.

.. autonamespace:: basilisp.tools.namespace.parse
   :members:

.. autonamespace:: basilisp.tools.namespace.dependency
   :members:

.. autonamespace:: basilisp.tools.namespace.file
   :members:

.. autonamespace:: basilisp.tools.namespace.find
   :members:

.. autonamespace:: basilisp.tools.namespace.dir
   :members:

.. autonamespace:: basilisp.tools.namespace.track
   :members:

.. autonamespace:: basilisp.tools.namespace.reload
   :members:

.. autonamespace:: basilisp.tools.namespace.repl
   :members:
