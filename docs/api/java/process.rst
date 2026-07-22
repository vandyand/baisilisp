basilisp.java.process
======================

``basilisp.java.process`` provides the ``clojure.java.process`` import path for
the portable subprocess contract. ``start``, stream accessors, ``exit-ref``,
``to-file``, ``from-file``, ``io-task``, and ``exec`` retain their Clojure-shaped
interfaces while returning Python :external:py:class:`subprocess.Popen` and
Future objects.

Python-specific stream encodings and path/file-object redirect extensions remain
available through the standard alias. Python-only helpers such as
``communicate`` remain on :lpy:ns:`basilisp.process` rather than the
``clojure.java.process`` alias.

.. autonamespace:: basilisp.java.process
   :members:
   :undoc-members:
