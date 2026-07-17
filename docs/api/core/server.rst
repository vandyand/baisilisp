basilisp.core.server
====================

``basilisp.core.server`` supplies the portable socket-server lifecycle subset of
``clojure.core.server`` and is available through that import path. A named server
binds text streams to ``*in*`` and ``*out*`` while it invokes its ``:accept``
function, so ``io-prepl`` can be used directly as an accept function.

The server registry is process-local and atomically owns names. Servers default
to ``127.0.0.1`` and daemon accept/client threads. ``start-servers`` accepts
``clojure.server.<name>`` entries in a supplied mapping; each value is an EDN
options map. General JVM socket REPL hooks (``repl``, ``repl-init``, and
``repl-read``) are intentionally not exposed because they depend on JVM REPL
hooks rather than the portable structured pREPL boundary.

.. autonamespace:: basilisp.core.server
   :members:
   :undoc-members:
