.. _concurrency:

Concurrency
===========

``basilisp.concurrent`` provides Python-native concurrency helpers alongside
the portable agent operations in :lpy:ns:`basilisp.core`.

The namespace deliberately exposes Python's concurrency model rather than
claiming JVM semantics. It provides application-owned thread executors,
executor submission and shutdown, agent status and synchronous waiting,
``asyncio`` task and queue helpers, and predicates for awaitable and asynchronous
iterable objects.

Agent Compatibility
-------------------

``agent``, ``send``, ``send-off``, ``send-via``, ``agent-error``, ``await1``,
and ``await-for`` are available from :lpy:ns:`basilisp.core`. Use
``basilisp.concurrent/wait`` for synchronous waiting because bare ``await`` is
reserved for async functions. ``await1`` retains Clojure's behavior of waiting
for a failed agent to be restarted.

Executor Ownership
------------------

``send-via`` accepts an application-owned thread executor for one agent action;
its workers must share the process memory that owns the agent.
Basilisp intentionally does not implement global executor replacement or
``shutdown-agents``: Python executors have explicit application ownership, and
replacing or shutting down shared process-wide executors would make unrelated
work fail unpredictably.

Async Channels
--------------

``basilisp.concurrent`` includes awaitable, ``asyncio``-native channels for
use inside ``defasync`` functions. ``chan`` creates a rendezvous channel by
default; pass a positive capacity for a fixed buffer, or a ``:sliding`` or
``:dropping`` policy for non-blocking buffer behavior.

Use ``await`` with ``put!`` and ``take!``. ``close!`` wakes blocked puts with
``false`` and causes future takes to return ``nil`` after buffered values are
drained. ``offer!`` and ``poll!`` provide non-blocking operations. Channels do
not accept ``nil`` values, reserving it as the closed-channel take result.

``alts!``, timeout channels, transducers, and a ``go`` macro are not yet
implemented. ``defasync`` and ``await`` are the intended Python-native
equivalent of the initial ``go``-block use case.

Transactions
------------

This namespace does not yet provide ``ref`` or ``dosync``. A transactional
reference API must establish conflict detection, retry behavior, atomic
multi-reference commit, and a policy for side effects before it can offer a
credible compatibility contract.
