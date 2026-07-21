basilisp.core.rrb-vector
=========================

``basilisp.core.rrb-vector`` provides the standard
``clojure.core.rrb-vector`` import path: ``vector``, ``vec``, ``vector-of``,
``catvec``, and non-view ``subvec``. Values use Basilisp's ordinary immutable
persistent-vector representation; the JVM's RRB node layout and primitive
unboxing are intentionally host-specific optimizations rather than observable
API guarantees.

.. autonamespace:: basilisp.core.rrb-vector
   :members:
   :undoc-members:
