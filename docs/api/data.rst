basilisp.data
=============

``basilisp.data`` provides the portable ``clojure.data`` diffing surface,
including ``Diff``, ``EqualityPartition``, ``diff``, ``diff-similar``, and
``equality-partition``. The standard ``clojure.data`` import path is rewritten
to this namespace when running under Basilisp.

Python-native containers passed to ``diff`` are converted to Basilisp data
structures before comparison. Custom extension should use the Clojure-compatible
``Diff`` and ``EqualityPartition`` protocols.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. autonamespace:: basilisp.data
   :members:
   :undoc-members:
