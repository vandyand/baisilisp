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

``server-make`` creates a loopback-only TCP server with newline-delimited EDN
events. Each connection gets an isolated namespace and ends when its client
closes the write side of the socket. Input is incrementally buffered so source
text remains available to ``prepl`` and is bounded to 1 MiB by default; pass
``:max-input-chars`` in the options map to change that limit.

CLI exposure, authentication, and interruption controls remain later
milestones.

.. autonamespace:: basilisp.contrib.prepl
   :members:
   :undoc-members:
   :exclude-members: IStreamOut, StreamOutFn
