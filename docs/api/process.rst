basilisp.process
================

The same portable process surface is available from the standard
``clojure.java.process`` import path through :lpy:ns:`basilisp.java.process`.
It uses Python :external:py:class:`subprocess.Popen` streams and Futures rather
than Java ``Process`` values; text-mode pipes follow Python's normalized ``\n``
newline behavior.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. autonamespace:: basilisp.process
   :members:
   :undoc-members:
   :exclude-members: FileWrapper, SubprocessRedirectable, ->FileWrapper, is-file-like?, is-path-like?
