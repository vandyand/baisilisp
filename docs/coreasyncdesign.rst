.. _core_async_design:

``core.async`` Compatibility Design
===================================

Purpose
-------

BaisiLisp should close as much of the ``clojure.core.async`` gap as is
practical without hiding Python's runtime model. The compatibility target is
source portability for ordinary Clojure programs that use channels, selection,
pipelines, and eventually ``go`` blocks. The implementation target is an
``asyncio``-native runtime that is predictable in Python applications.

This document is a design checkpoint before implementation. It separates:

* API that can be provided now as a compatibility facade over
  ``basilisp.concurrent``.
* API that needs new channel/runtime behavior but not compiler support.
* API that requires compiler support for ``go``/parking semantics.
* JVM-specific behavior that should be mapped explicitly or rejected.

Primary Compatibility Contract
------------------------------

The Clojure reference surface is ``clojure.core.async``. Its public API
includes channel constructors, buffer constructors, parking operations,
blocking operations, selection, pipelines, pub/sub, mult/mix, thread helpers,
and flow support.

The core contracts most relevant to BaisiLisp are:

* ``chan`` creates an optionally buffered channel; a numeric buffer argument
  creates a fixed buffer. Channels do not accept ``nil`` values because
  ``nil`` is the closed-channel take result.
* ``close!`` stops future puts while still allowing already buffered values to
  be taken. Once drained, takes return ``nil``.
* ``<!`` and ``>!`` are parking operations and must be used inside
  ``go`` blocks.
* ``<!!`` and ``>!!`` are blocking operations and are not intended for use
  inside ``go`` blocks.
* ``alts!`` chooses at most one take or put operation inside ``go`` blocks;
  ``alts!!`` is the blocking equivalent. ``:priority`` preserves supplied
  order, otherwise ready operations are selected non-deterministically.
  ``:default`` returns immediately when no operation is ready.
* ``go`` returns immediately with a channel that receives the body's result
  when the body completes.
* ``thread``/``thread-call`` run ordinary blocking work in a thread and return
  a channel that receives the result, then closes.

The official API index and source are the authority for these details:
`core.async API docs <https://clojure.github.io/core.async/>`_,
`async.clj <https://github.com/clojure/core.async/blob/master/src/main/clojure/clojure/core/async.clj>`_,
and the official
`walkthrough <https://github.com/clojure/core.async/blob/master/examples/walkthrough.clj>`_.

Current BaisiLisp Baseline
--------------------------

``basilisp.concurrent`` already has a useful Python-native channel
runtime:

* ``chan`` creates loop-bound ``asyncio`` channels with rendezvous, fixed,
  sliding, and dropping policies.
* ``put!`` and ``take!`` are awaitable operations.
* ``close!``, ``closed?``, ``offer!``, and ``poll!`` provide close and
  non-blocking operations.
* ``alts!`` awaits one take channel or ``[channel value]`` put operation and
  supports ``:priority`` and ``:default``.
* ``timeout`` returns a one-shot channel that closes after a delay.
* ``pipe!`` forwards values from one channel to another.
* ``pipeline!`` provides bounded ordered fan-out for synchronous transducers.
* ``defasync`` and ``await`` provide direct Python coroutine interop.

The implementation is intentionally ``asyncio``-native:

* Channels bind to the event loop that first uses them.
* Operations are cancellable and remove their pending waiter on cancellation.
* ``nil`` values are rejected.
* Closed takes return ``nil`` after buffered values drain.
* Closed puts return ``false``.

This is the right substrate. BaisiLisp now has an initial
``clojure.core.async`` facade backed by ``basilisp.core.async`` and the
existing channel runtime. The public surface is now closed by a
coroutine-backed ``go``/parking subset; the important remaining caveat is that
this is not Clojure's compiler-produced IOC state-machine implementation.

Design Principles
-----------------

1. Prefer honest compatibility.
   If an API is only Python-native, expose it from
   ``basilisp.concurrent``. Add it to ``clojure.core.async`` only when
   the observable contract is close enough or the deviation is documented and
   tested.

2. Preserve Python event-loop ownership.
   BaisiLisp channels must not pretend to be JVM channels that can be blocked
   on from any OS thread. Cross-thread and blocking adapters must be explicit
   bridges around an owning event loop.

3. Make unsupported behavior fail deterministically.
   A partial ``go`` implementation should reject unsupported forms at compile
   time or macro expansion time. Silent fallback to blocking Python behavior is
   worse than a clear error.

4. Keep Python-native async ergonomic.
   ``defasync`` and ``await`` should remain the recommended interface for
   Python applications even after ``go`` exists. ``go`` is primarily a Clojure
   source-compatibility feature.

5. Prove concurrency behavior with stress and reference tests.
   Channel races must be covered with deterministic edge-case tests and
   randomized cancellation/producer/consumer traces. Source-compatible cases
   should be compared against JVM ``core.async`` where possible.

Namespace Shape
---------------

Add a new compatibility namespace:

.. code-block:: clojure

   (ns clojure.core.async)

The namespace should wrap or re-export compatible pieces from
``basilisp.concurrent``. Existing Python-native names remain available
there, while portable Clojure source can require:

.. code-block:: clojure

   (require '[clojure.core.async :as async])

The namespace should begin intentionally small and grow behind tests. A stub
namespace that advertises unavailable macros would be worse than no namespace.

Compatibility Matrix
--------------------

The first implementation pass should classify every public ``core.async`` name
into one of these states:

.. list-table::
   :header-rows: 1

   * - State
     - Meaning
     - Examples
   * - Available now
     - Can be implemented as a direct wrapper over current channel behavior.
     - ``close!``, ``offer!``, ``poll!``, ``timeout``
   * - Adapter now
     - Requires Clojure-shaped argument handling around current behavior.
     - ``chan``, ``buffer``, ``dropping-buffer``, ``sliding-buffer``,
       ``alts!`` outside ``go`` as an awaitable extension
   * - Runtime work
     - Requires new channel combinators but not compiler transformation.
     - Covered locally for ``pipeline-blocking`` and ``pipeline-async``.
       Larger lifecycle combinators remain separate design work.
   * - Compiler work
     - Requires ``go``/parking context or macro lowering.
     - Public surface covered locally by coroutine-backed ``go``, ``go-loop``,
       ``<!``, ``>!``, and ``alt!``. Full Clojure IOC/state-machine parity,
       including meaningful direct ``ioc-alts!`` integration, remains deeper
       compiler work.
   * - Blocking bridge
     - Requires an explicit policy for using a loop-owned async channel from
       synchronous Python threads.
     - Covered locally for ``<!!``, ``>!!``, ``alts!!``, ``alt!!``,
       ``fn-handler``, ``do-alts``, ``do-alt``, ``defblockingop``,
       ``thread``, and ``thread-call``/``io-thread``. ``alt!!`` is a source
       macro over ``alts!!``. ``do-alts`` exposes the immediate-or-enqueued
       helper shape used by Clojure's IOC layer. ``io-thread`` currently
       preserves the public macro shape and routes through the same
       worker-thread executor as ``thread``.
   * - Advanced routing
     - Requires higher-level fan-out/fan-in state and lifecycle semantics.
     - Covered locally for ``mult``/``pub``/``mix`` families; remaining flow
       APIs are deferred.
   * - Defer
     - Experimental or broad enough to need a separate design.
     - ``clojure.core.async.flow``

Phase 1: Compatibility Facade Without ``go``
--------------------------------------------

The first implementation tranche adds ``clojure.core.async`` with the
non-compiler subset.

Proposed public functions/macros:

* ``buffer``
* ``dropping-buffer``
* ``sliding-buffer``
* ``chan``
* ``close!``
* ``offer!``
* ``poll!``
* ``put!``
* ``take!``
* ``alts!`` as an awaitable BaisiLisp extension, clearly documented until
  ``go`` exists
* ``timeout``
* ``pipe``
* ``pipeline``
* ``pipeline-blocking``
* ``pipeline-async``
* ``promise-chan``
* ``to-chan`` / ``to-chan!`` / ``to-chan!!``
* ``onto-chan`` / ``onto-chan!`` / ``onto-chan!!``
* ``map``
* ``partition``
* ``partition-by``
* ``unique``
* ``unblocking-buffer?``
* ``map<`` / ``map>``
* ``filter<`` / ``filter>``
* ``remove<`` / ``remove>``
* ``mapcat<`` / ``mapcat>``
* ``Mux`` / ``Mult`` / ``Pub`` / ``Mix`` protocol markers
* ``muxch*``
* ``mult`` / ``tap`` / ``untap`` / ``untap-all``
* ``tap*`` / ``untap*`` / ``untap-all*``
* ``pub`` / ``sub`` / ``unsub`` / ``unsub-all``
* ``sub*`` / ``unsub*`` / ``unsub-all*``
* ``mix`` / ``admix`` / ``unmix`` / ``unmix-all`` / ``toggle`` /
  ``solo-mode``
* ``admix*`` / ``unmix*`` / ``unmix-all*`` / ``toggle*`` / ``solo-mode*``
* ``<!!`` / ``>!!`` / ``alts!!``
* ``thread`` / ``thread-call`` / ``io-thread``

The buffer constructors should return small Basilisp data objects or Python
objects that describe policy and capacity:

.. code-block:: clojure

   (buffer 10)           ; fixed buffer
   (dropping-buffer 10)  ; dropping buffer
   (sliding-buffer 10)   ; sliding buffer

``chan`` should accept the Clojure argument shape:

.. code-block:: clojure

   (chan)
   (chan 10)
   (chan (sliding-buffer 10))
   (chan (dropping-buffer 10))

Transducer arguments are supported for synchronous xforms. The channel applies
the xform at put time, supports zero/one/many emitted values, honors
``ex-handler`` replacement/drop behavior, and flushes completing transducers on
``close!`` where the output can be delivered to the channel.

``put!`` and ``take!`` are tricky because Clojure's public functions are
callback-oriented and return immediately, while BaisiLisp's current functions
return awaitables. Phase 1 should choose one of these policies and test it:

* Prefer compatibility wrappers that accept optional callbacks and schedule
  the awaitable operation on the current event loop.
* Keep the awaitable return as a documented BaisiLisp extension when no
  callback is supplied.
* Reject calls made outside a running event loop unless a blocking bridge has
  been selected explicitly.

That gives practical Clojure-shaped source without pretending that all
synchronous/JVM semantics are present.

Phase 2: Blocking Bridge
------------------------

Blocking ``core.async`` operations are useful for tests and REPL workflows, but
they are where Python differences matter most.

The bridge must answer these questions before implementation:

* Which event loop owns the channel?
* Is that loop currently running?
* Is the caller already inside that loop?
* Who owns loop startup and shutdown?

Design:

* ``<!!``, ``>!!``, and ``alts!!`` should reject calls from the owning running
  event-loop thread. Blocking the loop would deadlock.
* From another thread, they may use ``asyncio.run_coroutine_threadsafe`` when
  the channel's loop is running.
* For an unbound channel, a blocking call may create and own a temporary event
  loop only if it can prove no other task needs to rendezvous with that
  channel. In practice, this should probably be rejected for rendezvous
  operations and accepted only for immediate buffered/closed operations.
* Tests should cover cross-thread success, same-loop rejection, timeout/cancel
  cleanup, closed channels, and rendezvous deadlock prevention.

``thread``, ``thread-call``, and ``io-thread`` can be mapped to the existing
executor helpers. They should return a one-value channel and close it when the
function exits. Like Clojure, a ``nil`` result means there is no value to put
and the channel closes. ``io-thread`` preserves Clojure's macro shape and
passes the ``:io`` workload hint through ``thread-call``; BaisiLisp currently
uses the same worker-thread executor for both workloads. Exceptions should be
specified and tested against Clojure behavior before implementation; the safe
first policy is to close the channel and route the exception to the Python
task/thread exception handler rather than placing an exception object on the
channel.

Phase 3: Minimal ``go`` As Coroutine Lowering
---------------------------------------------

The smallest useful ``go`` implementation can be coroutine-based:

.. code-block:: clojure

   (go
     (>! out (inc (<! in))))

Conceptually lowers to:

.. code-block:: clojure

   (let [result-ch (chan 1)]
     (task
       ((fn ^:async []
          (try
            (let [ret (do
                        (await (put! out (inc (await (take! in))))))]
              (when-not (nil? ret)
                (await (put! result-ch ret))))
            (finally
              (close! result-ch))))))
     result-ch)

This gets a useful amount of source compatibility but is not a full Clojure
state-machine implementation. The current tranche therefore documents a clear
boundary:

* ``<!`` expands to an await of ``take!`` and is valid where Basilisp permits
  ``await``. Portable Clojure-shaped use should keep it inside ``go``.
* ``>!`` expands to an await of ``put!`` and is valid where Basilisp permits
  ``await``. Portable Clojure-shaped use should keep it inside ``go``.
* ``alt!`` expands to awaitable selection over ``alts!``.
* ``<!!``, ``>!!``, and ``alts!!`` inside ``go`` are not currently rejected at
  macro-expansion time; they retain the existing same-owner-loop deadlock
  rejection when invoked.
* Arbitrary Python blocking calls cannot be detected reliably; docs should
  warn that they block the event loop or task runner.
* ``go`` returns a channel immediately.
* On normal completion, a non-``nil`` result is placed on the result channel
  and then the result channel is closed.
* If the body returns ``nil``, the result channel closes without a value.
* If the body throws, the result channel closes without a value. Shared JVM
  fixtures cover the observable channel result; BaisiLisp still reports the
  task exception according to normal Python task/future rules rather than
  exposing a Clojure IOC exception channel.

This phase should be documented as a source-compatibility subset. It provides
ordinary ``go`` examples, but it does not claim full IOC/state-machine parity.

Phase 4: Compiler-Backed Parking State Machine
----------------------------------------------

Full ``go`` parity requires compiler involvement. Clojure's implementation
does not merely wrap a body in a normal async function; it transforms eligible
control flow into a resumable state machine. BaisiLisp can defer this until the
coroutine subset proves useful, but the design should leave room for it.

A compiler-backed ``go`` should:

* Analyze the body in a special parking context.
* Rewrite ``<!``, ``>!``, ``alts!``, and ``alt!`` into suspension points.
* Preserve lexical bindings across suspension.
* Support ``loop``/``recur`` and ordinary expression control flow.
* Define supported ``try``/``catch``/``finally`` behavior.
* Reject unsupported forms deterministically.
* Avoid requiring a Python ``await`` to cross an ordinary function boundary.

The state-machine path is more work, but it is the route to real
``core.async`` parity. It should be attempted only after the channel runtime
and compatibility namespace have strong tests.

Phase 5: Higher-Level Channel Operations
----------------------------------------

The non-``go`` pipeline variants are now built as ordinary channel processes
over the same runtime, not as separate concurrency primitives. Future
higher-level operations should follow the same rule: each operation needs
explicit lifecycle rules for whether it closes outputs, whether it owns tasks,
what happens when consumers close early, and how cancellation propagates.

Python Primitive Boundaries
---------------------------

The following Python constraints are not incidental; they are part of the
BaisiLisp contract:

* ``asyncio`` event loops are thread-affine. A channel cannot be transparently
  shared across arbitrary loops.
* Python has native awaitables, tasks, futures, async iterables, and queues.
  BaisiLisp should interoperate with them directly rather than hide them under
  JVM terminology.
* Blocking calls inside the running event-loop thread are bugs. Compatibility
  wrappers should reject them clearly.
* Cancellation is observable in Python. Pending channel operations must remove
  their waiters and avoid lost values.
* Python exceptions are not channel values. Unless a Clojure API explicitly
  defines exception-as-value behavior, exceptions should remain exceptions.

Testing Strategy
----------------

Every phase should add tests before broadening the public surface.

1. Public API inventory
   A test should enumerate ``clojure.core.async`` publics in BaisiLisp and
   compare them to a maintained support matrix.

2. JVM differential fixtures
   Small source fixtures should run on Clojure/JVM and BaisiLisp where both
   sides can observe the same values. Good early cases: close semantics,
   buffer policies, nil rejection, ``alts`` priority/default, pipeline order,
   and result-channel lifecycle.

3. Python runtime stress tests
   Existing tests should be extended with random producer/consumer schedules,
   cancellation while parked, close races, cross-thread blocking bridges, and
   task-leak checks.

4. Rejection tests
   Unsupported parking forms, blocking calls in ``go``, same-loop blocking
   bridge calls, nil channel values, and unsupported flow APIs should fail with
   stable messages.

5. Documentation tests
   Examples in ``docs/concurrency.rst`` and this design should compile or be
   explicitly marked as design-only.

Completed Facade Tranche
------------------------

The initial implementation now covers:

* Add ``buffer``, ``dropping-buffer``, and ``sliding-buffer`` descriptors.
* Make ``chan`` accept Clojure-shaped buffer arguments and delegate to the
  existing channel runtime.
* Re-export or wrap ``close!``, ``offer!``, ``poll!``, ``timeout``, ``pipe``,
  and ``pipeline``.
* Provide and test the phase-1 callback/awaitable behavior for ``put!`` and
  ``take!``: no callback returns an awaitable; callback calls schedule on the
  current event loop and return ``nil``.
* Add the coroutine-backed parking surface ``go``, ``go-loop``, ``<!``,
  ``>!``, and ``alt!``. ``ioc-alts!`` is public and rejects direct calls
  deterministically because the current implementation does not expose a
  Clojure-style IOC state machine.
* Harden the coroutine-backed parking subset with shared JVM fixtures for
  closed-channel takes, puts to closed channels, timeout interaction, nested
  ``alt!`` choices, close/result races, and exception-driven result-channel
  close behavior. Local runtime tests also cover current-loop ``go`` scheduling
  and deterministic same-owner-loop rejection when blocking calls are invoked
  from inside ``go``.
* Add the first collection/channel combinators: ``to-chan!``, ``onto-chan!``,
  ``merge``, ``split``, ``take``, ``into``, ``reduce``, and ``transduce``.
  These return channels and run their work in caller-owned ``asyncio`` tasks.
* Add the second collection/channel tranche: ``promise-chan``, ``to-chan``,
  ``to-chan!!``, ``onto-chan``, ``onto-chan!!``, ``map``, ``partition``,
  ``partition-by``, ``unique``, and ``unblocking-buffer?``. ``promise-chan``
  realizes one value and returns it repeatedly; the other combinators are
  covered by shared JVM fixtures.
* Add transform-direction combinators: ``map<``, ``map>``, ``filter<``,
  ``filter>``, ``remove<``, ``remove>``, ``mapcat<``, and ``mapcat>``. The
  ``<`` variants derive output channels from source channels; the ``>``
  variants return writable channels that transform/filter/fan-out into the
  supplied target channel.
* Add task-backed routing combinators: ``mult``, ``tap``, ``untap``,
  ``untap-all``, ``pub``, ``sub``, ``unsub``, and ``unsub-all``. The current
  publication implementation models Clojure's per-topic internal channels:
  ``buf-fn`` is called once when a topic is first subscribed, unsubscribed
  topics do not allocate buffers, and ``unsub-all`` removes topic state so a
  later subscription recreates it.
* Add the routing protocol helper surface: ``Mux``, ``Mult``, ``Pub``,
  ``Mix``, ``muxch*``, and the ``tap*``/``sub*``/``admix*`` helper families.
  These delegate to the existing map-backed routing state and preserve the
  portable return values covered by JVM fixtures.
* Add the ``mix`` routing family: ``mix``, ``admix``, ``unmix``,
  ``unmix-all``, ``toggle``, and ``solo-mode``. The implementation supports
  Clojure's ``:mute``, ``:pause``, and ``:solo`` state maps, including both
  default solo muting and ``solo-mode :pause``.
* Add blocking/thread bridges and helper publics: ``<!!``, ``>!!``,
  ``alts!!``, ``alt!!``, ``fn-handler``, ``do-alts``, ``do-alt``,
  ``defblockingop``, ``thread``, and ``thread-call``. Blocking calls run
  against the channel's owner loop from synchronous callers and reject calls
  from that owner loop to avoid deadlock. ``alt!!`` uses the public ``do-alt``
  expansion helper and delegates to ``alts!!``. ``do-alts`` covers the public
  immediate/enqueued helper contract used by the eventual IOC layer.
* Add pipeline variants: ``pipeline-blocking`` delegates to the bounded
  worker-thread transducer pipeline, while ``pipeline-async`` accepts
  callback-shaped asynchronous work, preserves input order, handles fan-out,
  honors ``close?``, and stops admitting source values when the destination is
  closed.
* Add channel transducers for ``chan``: synchronous xforms run at put time,
  preserve state across puts, may emit zero/one/many values, flush completion
  output on close, honor ``ex-handler`` replacement/drop behavior, and close
  the channel when a completing xform such as ``take`` terminates.
* Harden the support matrix and IOC boundary: shared fixtures now require the
  ``clojure.core.async`` facade to have no missing or accidental extra public
  names, the source-level acceptance library emits the same exactness proof,
  and direct ``ioc-alts!`` calls fail with structured ``ex-data`` identifying
  the unsupported compiler-generated IOC state-machine boundary.

Why this tranche first:

* It immediately makes portable Clojure code start with the expected namespace.
* It reuses the channel runtime that already has good cancellation and
  ordering tests.
* It avoids compiler-risk until the public surface and argument semantics are
  stable.
* It creates the acceptance matrix needed to implement ``go`` without guessing.

Recommended Next Tranche
------------------------

The next tranche should decide whether deeper compiler-produced IOC parity is
worth the complexity or whether the coroutine-backed ``go`` subset is the
intended long-term compatibility boundary. The ``clojure.core.async`` public
surface is now exact and guarded, but public surface parity is not the same as
full implementation parity:

* Keep the maintained public support matrix for ``clojure.core.async`` exact in
  both the differential fixture and the source-level acceptance library.
* Extend JVM differential fixtures only where behavior is portable and
  observable from channels; the current hardening tranche already covers closed
  channels, timeout interaction, nested parking choices, close/result races, and
  exception result-channel lifecycle.
* Decide whether to keep ``ioc-alts!`` as an explicit unsupported boundary for
  the long term or invest in a compiler-produced state-machine representation.
* Add deterministic rejection or compatibility tests for any remaining
  unsupported flow APIs and for unsupported parking/compiler forms if deeper IOC
  work begins.
