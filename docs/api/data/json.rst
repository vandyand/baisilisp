basilisp.data.json
==================

``basilisp.data.json`` provides the ``clojure.data.json`` import path. Its
public surface includes the standard read/write functions, legacy helper names,
``JSONWriter``, default option maps, and compatibility placeholders for
data.json's host-specific pushback-reader constructors.

The implementation is backed by Python's JSON codec and returns Basilisp
persistent maps and vectors. Input and output use Python text streams rather
than JVM Reader/Writer or PushbackReader values.

.. autonamespace:: basilisp.data.json
   :members:
   :undoc-members:
