basilisp.data.csv
=================

``basilisp.data.csv`` provides the ``clojure.data.csv`` import path. Its
``read-csv`` and ``write-csv`` functions are backed by Python's standard CSV
support while preserving Clojure's separator, quote, quote-predicate, and
``:lf``/``:cr+lf`` writer options. Input and output are text streams; this is
not a Java Reader/Writer compatibility layer.

.. autonamespace:: basilisp.data.csv
   :members:
   :undoc-members:
