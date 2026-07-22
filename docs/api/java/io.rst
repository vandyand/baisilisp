basilisp.java.io
================

``basilisp.java.io`` provides the ``clojure.java.io`` import path for the
portable path, URL, reader, writer, stream, copy, and factory contracts backed
by :lpy:ns:`basilisp.io`.

Values are Python-backed rather than JVM-backed: ``file`` and ``as-file`` return
Python :external:py:class:`pathlib.Path` values, ``as-url`` returns parsed
``urllib`` URL values, and ``resource`` searches Python's import path instead of
using JVM class loaders. Python-only helpers such as ``path``, ``exists?``, and
``touch`` remain on :lpy:ns:`basilisp.io` rather than the standard
``clojure.java.io`` alias.

.. autonamespace:: basilisp.java.io
   :members:
   :undoc-members:
