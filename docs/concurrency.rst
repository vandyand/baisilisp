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

``agent``, ``send``, ``send-off``, ``agent-error``, and ``await-for`` are
available from :lpy:ns:`basilisp.core`. Use ``basilisp.concurrent/wait`` for
synchronous waiting because bare ``await`` is reserved for async functions.

Transactions
------------

This namespace does not yet provide ``ref`` or ``dosync``. A transactional
reference API must establish conflict detection, retry behavior, atomic
multi-reference commit, and a policy for side effects before it can offer a
credible compatibility contract.
