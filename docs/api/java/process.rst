basilisp.java.process
======================

``basilisp.java.process`` provides the ``clojure.java.process`` import path for
the portable subprocess contract. ``start``, stream accessors, ``exit-ref``,
``to-file``, ``from-file``, ``io-task``, and ``exec`` retain their Clojure-shaped
interfaces while returning Python :external:py:class:`subprocess.Popen` and
Future objects.

Python-specific stream encodings and path/file-object redirect extensions remain
available through :lpy:ns:`basilisp.process` and its aliased public surface.

.. autonamespace:: basilisp.java.process
   :members:
   :undoc-members:
