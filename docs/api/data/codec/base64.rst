basilisp.data.codec.base64
===========================

``basilisp.data.codec.base64`` provides the ``clojure.data.codec.base64``
import path. Its public surface covers byte-array length helpers, encode/decode
functions, mutable-destination ``encode!``/``decode!`` operations, and binary
stream transfer helpers.

The implementation accepts Python bytes-like values and binary streams in place
of JVM byte arrays and streams. Decode behavior intentionally follows
``clojure.data.codec.base64``: malformed alphabet bytes are decoded through the
same permissive table-based contract rather than Python's strict validation
mode.

.. autonamespace:: basilisp.data.codec.base64
   :members:
   :undoc-members:
