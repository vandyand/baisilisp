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

``agent``, ``send``, ``send-off``, ``send-via``, ``agent-error``, ``await``,
``await1``, and ``await-for`` are available from :lpy:ns:`basilisp.core`.
Bare ``await`` remains the Python async special form, so synchronous Clojure
agent waiting uses the qualified ``clojure.core/await`` or
``basilisp.core/await`` spelling. ``basilisp.concurrent/wait`` remains a
clear Python-facing alias for the non-failure-blocking ``await-agent`` helper.
Within an action, dynamic ``*agent*`` is the target agent; it is ``nil``
outside an action. Ordinary dynamic bindings from the sender are conveyed to
the action, but a caller's own ``*agent*`` binding cannot replace that target.
``await`` and ``await-for`` reject transaction and agent-action contexts;
they add Clojure-style barrier actions and a settled failed agent rejects that
dispatch. ``await1`` waits only for pending work and returns its agent, so an
already failed agent returns immediately.

Executor Ownership
------------------

``send-via`` accepts an application-owned thread executor for one agent action;
its workers must share the process memory that owns the agent.
``set-agent-send-executor!`` and ``set-agent-send-off-executor!`` replace the
process-wide executors used by future ``send`` and ``send-off`` calls. Queued
actions retain the executor selected at dispatch time; the caller owns any
replacement and prior executors. ``shutdown-agents`` initiates non-blocking
shutdown of the current global executors, allowing running actions to complete
while rejecting new ones. ``release-pending-sends`` returns zero: Basilisp
dispatches ordinary nested sends immediately, while transaction sends remain
deferred until commit.

Queued Sequences
----------------

``basilisp.core/seque`` provides Clojure-compatible queued lazy sequences
without exposing a global Agent executor. It starts a daemon producer which may
realize up to the configured positive buffer size ahead of consumption; callers
may instead provide a Python queue object with ``put`` and ``get`` methods.
Reading ahead of the producer blocks. As in Clojure, a producer exception is
reported and terminates the queued sequence rather than becoming a value.

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

``alts!`` awaits exactly one take channel or ``[channel value]`` put operation
and returns ``[value channel]``. ``:priority true`` checks ready operations in
order; otherwise ready operations are selected fairly. ``:default value``
returns ``[value :default]`` without waiting. ``timeout`` creates a one-shot
channel that closes after its delay. A cancelled ``alts!`` call removes all of
its pending operations.

Transducers, pipelines, pub/sub, and a ``go`` macro are not yet implemented.
``defasync`` and ``await`` are the intended Python-native equivalent of the
initial ``go``-block use case.

Transactions
------------

``basilisp.core`` provides a synchronous ``Ref`` and ``dosync`` surface.
``dosync`` retries a transaction when an observed Ref version changes before
commit, and commits all staged ``alter`` and ``ref-set`` writes together. Refs
support the usual validators, metadata, and watches. Transaction bodies must
be side-effect free and must not return awaitables because they can run more
than once.

``sync`` is also provided for existing Clojure source. Its leading transaction
flags argument is accepted and ignored, matching Clojure's documented current
behavior; new Basilisp code should normally use ``dosync``.

``commute`` replays its update function against the latest committed value and
therefore requires a retry-safe, commutative function. ``ensure`` marks a Ref
for normal version validation when a transaction would otherwise use only
commute semantics. History controls remain intentionally unimplemented. ``io!``
is an explicit guard for known impure operations, and agent dispatches inside
``dosync`` are deferred until a successful commit; neither mechanism can detect
arbitrary Python side effects in a retried transaction body.

``dosync`` retries until it can commit. The Basilisp-specific
``run-transaction`` function accepts a positive ``:max-attempts`` option for
callers that need a bounded retry policy. If the final attempt conflicts it
raises ``ExceptionInfo`` with ``:basilisp.stm/attempts`` and a
``:basilisp.stm/conflicts`` vector whose entries include each Ref identity and
the observed/current version numbers.
