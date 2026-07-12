basilisp.contrib.prepl
======================

.. lpy:currentns:: basilisp.contrib.prepl

Structured REPL Events
----------------------

``prepl`` evaluates forms from a reader and sends ordered event maps to a
callback. Successful forms produce one ``:ret`` event with the evaluated value,
namespace, elapsed milliseconds, and original source text. Output produces one
or more ``:out`` or ``:err`` events; reader and evaluation failures are
represented by ``:ret`` events with ``:exception true`` and structured error
data.

``io-prepl`` is the stream-oriented variant. It consumes ``*in*`` and writes
one readable EDN event per line to ``*out*``. Return and tap values are printed
with ``pr-str`` by default so Python objects are not serialized across a
transport boundary.

The local APIs do not open sockets. A remote pREPL server remains a later
milestone, after session isolation, framing, authentication, and interruption
semantics have explicit contracts.

.. autonamespace:: basilisp.contrib.prepl
   :members:
   :undoc-members:
   :exclude-members: IStreamOut, StreamOutFn
