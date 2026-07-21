basilisp.tools.reader
======================

``basilisp.tools.reader`` provides the portable ``clojure.tools.reader``
single-form reader API. Use ``clojure.tools.reader.reader-types`` constructors
when repeatedly reading a stream; they retain parser lookahead and expose
pushback, line/column, and source-logging operations.

``read+string`` requires a source-logging pushback reader and returns a vector
of the form and its whitespace-trimmed source text. Reader conditionals,
tagged-literal reader bindings, and syntax-quote use Basilisp's native reader
semantics. JVM-only reader evaluation and Java class construction are not
provided.

.. autonamespace:: basilisp.tools.reader
   :members:
   :undoc-members:

.. autonamespace:: basilisp.tools.reader.reader-types
   :members:
   :undoc-members:
