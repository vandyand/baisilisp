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

The deprecated root helpers ``find-ns-decls-on-classpath`` and
``find-namespaces-on-classpath`` scan Basilisp's Python import path
(``sys.path``) rather than a JVM classpath. They include directories and
ZIP/JAR archives and use the Basilisp ``:lpy`` platform, so ``.lpy`` and
portable ``.cljc`` sources are discovered.

The source-moving refactoring API from upstream is exposed for source
compatibility. It is labelled alpha upstream, is destructive, and performs a
pure textual rewrite; use it only in version-controlled or disposable source
trees.

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

.. autonamespace:: basilisp.tools.namespace.move
   :members:
