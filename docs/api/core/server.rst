basilisp.core.server
====================

``basilisp.core.server`` supplies portable socket-server lifecycle and REPL
support compatible with ``clojure.core.server`` and is available through that
import path. A named server binds text streams to ``*in*`` and ``*out*`` while it
invokes its ``:accept`` function, so both ``io-prepl`` and ``repl`` can be used
directly as accept functions.

The server registry is process-local and atomically owns names. Servers default
to ``127.0.0.1`` and daemon accept/client threads. ``start-servers`` accepts
``clojure.server.<name>`` entries in a supplied mapping; each value is an EDN
options map. ``repl`` starts in ``user``, makes ``basilisp.repl`` helpers
available, retains normal REPL history, and exits on EOF or ``:repl/quit``.
``repl-read`` has Clojure's hook signature and quit handling; unlike the JVM
reader hook, it cannot emit a line-start prompt sentinel because Python text
readers do not expose that state.

.. autonamespace:: basilisp.core.server
   :members:
   :undoc-members:
