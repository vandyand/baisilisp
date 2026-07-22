basilisp.data.csv
=================

``basilisp.data.csv`` provides the ``clojure.data.csv`` import path. Its
``Read-CSV-From`` protocol plus ``read-csv``, ``read-csv-from``, and
``write-csv`` functions are backed by Python's standard CSV support while
preserving Clojure's separator, quote, quote-predicate, and ``:lf``/``:cr+lf``
writer options. Input and output are Python text streams rather than Java
Reader/Writer values.

.. autonamespace:: basilisp.data.csv
   :members:
   :undoc-members:
