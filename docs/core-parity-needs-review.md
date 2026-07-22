# Clojure Core Parity Classification

This document classifies the 24 symbols reported missing by the refreshed
`core_parity_matrix.py` run on 2026-07-21 (655 shared Vars and 59 Basilisp
extensions). The matrix is a raw public-var
comparison, so it includes Clojure implementation details and Java-runtime
facilities in addition to portable user APIs.

The goal is to implement every portable API with tests. Symbols in **Needs
review** must not receive a compatibility-shaped stub: their documented Clojure
behavior depends on the JVM, Clojure's compiler internals, or its STM/agent
runtime. A Basilisp fork needs an explicit Python-native design before exposing
one of those names.

## Implemented

The following symbols are now implemented and no longer appear as gaps:

`alias`, `array-map`, `bound?`, `comparator`, `create-struct`, `defstruct`,
`accessor`,
`agent`, `agent-error`, `agent-errors`, `await-for`, `clear-agent-errors`, `error-handler`,
`error-mode`, `find-protocol-impl`, `find-protocol-method`, `line-seq`,
`io!`, `list*`, `locking`, `hash-combine`, `hash-ordered-coll`, `hash-unordered-coll`,
`mix-collection-hash`, `num`, `partitionv`, `partitionv-all`, `re-groups`,
`re-matcher`, `read+string`, `reductions`, `replicate`, `splitv-at`, `struct`,
`struct-map`, `subseq`, `rsubseq`, `sorted-map`, `sorted-map-by`, `sorted?`,
`sorted-set`, `sorted-set-by`, `restart-agent`, `send`, `send-off`, `send-via`,
`set-error-handler!`, `set-error-mode!`, `test`, `unsigned-bit-shift-right`,
and `xml-seq`, plus `+'`, `-'`, `*'`, `await1`, `ref`, `dosync`, `alter`, `ref-set`,
`commute`, `ensure`, `ref-history-count`, `ref-min-history`, `ref-max-history`,
`sync`, `seque`, `print-method`, `print-dup`, `print-simple`, and `print-ctor`.
``*math-context*`` and ``with-precision`` now provide Clojure-compatible
dynamic decimal context behavior: nil selects unlimited exact BigDecimal
arithmetic, while finite contexts restore after nested bindings and default to
``HALF_UP`` rounding.
The agent lifecycle names `await`, `release-pending-sends`,
`set-agent-send-executor!`, `set-agent-send-off-executor!`, and
`shutdown-agents` are also implemented. Bare ``await`` remains Basilisp's async
special form, so the Clojure agent wait is available as the qualified
``clojure.core/await`` or ``basilisp.core/await`` spelling.
The Python-host compatibility forms `bean`, `enumeration-seq`, `uri?`,
`StackTraceElement->vec`, and `Throwable->map` are also implemented.
``*file*`` is dynamically bound to the active source path during compilation,
macro expansion, module loading, and cached-bytecode execution. It is ``nil``
for interactive input; nested ``eval`` preserves its enclosing source binding.
``*source-path*`` follows the same source lifecycle with Clojure's
``"NO_SOURCE_FILE"`` interactive sentinel, while retaining its historical
thread-bindable-but-metadata-neutral Var shape.
``*read-eval*`` now controls Clojure-compatible ``#=`` evaluation in the core
reader APIs. Bind it to ``false`` to reject reader evaluation, or ``:unknown``
to require an explicit true/false policy before any read.
``*reader-resolver*`` now controls alias and syntax-quote resolution in those
same reader APIs, while preserving bindings to Basilisp's older ``*resolver*``
spelling.
``*agent*`` is dynamically bound to the executing target during every agent
action, and remains ``nil`` outside one.
``definline`` now defines Clojure-compatible callable functions and inline
expansions together, using Basilisp's existing compiler inlining controls.
``*repl*`` is now true while CLI, socket, and session-backed interactive REPLs
evaluate a form, and false outside that context.
``*verbose-defrecords*`` now matches Clojure's duplicate-printing switch:
with ``*print-dup*`` true, false renders the compact positional record form
and true renders the full map form, including extension entries.
``*suppress-read*`` now preserves every tagged literal as data while bound,
including otherwise built-in tags; ordinary reads still resolve registered tags
and reject unknown ones.
``create-struct`` now creates an identity-bearing fixed-key basis. ``struct``
and ``struct-map`` retain those fixed keys while allowing removable extension
keys, and ``accessor`` accepts only values built from its exact basis.
``print-simple`` now writes Clojure-style qualifying metadata followed by the
ordinary string representation. ``print-ctor`` likewise accepts Clojure's
writer callback shape, with the explicitly Python-hosted
``module.Qualname`` type label in place of a JVM class name.
``*clojure-version*`` and ``clojure-version`` now declare the Clojure 1.12.4
source-compatibility target used by the differential corpus. They never claim
that Basilisp is a Clojure runtime; ``*basilisp-version*`` remains the
Python-hosted implementation identity.
``seq-to-map-for-destructuring`` now follows Clojure's 1.11 public
keyword-argument sequence contract: empty sequences yield an empty map,
singletons remain unchanged, and longer even sequences become maps.
``proxy-call-with-super`` temporarily disables a proxy method mapping and
restores it in ``finally``. ``proxy-name`` reports the stable cached Python
``module.Qualname`` label for a superclass/interface set, rather than a JVM
generated-class name.
``*allow-unresolved-vars*`` now creates a compiler context that accepts an
otherwise unresolved symbol and, as in Clojure, raises only when that compiled
unresolved Var expression is evaluated. It remains false by default, is
thread-bindable, and macroexpansion retains its long-standing ability to return
unresolved forms as data.
``chunk-buffer``, ``chunk-append``, ``chunk``, ``chunk-cons``, ``chunk-first``,
``chunk-rest``, ``chunk-next``, and ``chunked-seq?`` now share an immutable,
indexed Python chunk model. Vector sequences use 32-element chunks, buffers are
bounded and one-shot, and chunks intentionally remain indexed/countable values
rather than ordinary sequences. ``->ArrayChunk`` retains Clojure's positional
manager argument but ignores it because Python sequences need no JVM
``ArrayManager``. Realized ``map``, ``map-indexed``, ``filter``, ``keep``,
``keep-indexed``, and ``concat`` preserve those chunk boundaries, including
Clojure's one-chunk-ahead realization behavior.
``with-local-vars`` is also available with thread-local Var-cell semantics.

## Portable Implementation Targets

These symbols have useful public behavior that can be ported without claiming
to reproduce JVM internals. They remain implementation work, not review
deferrals.


## Needs Review

### Clojure compiler, reader, and Java class-loader state

`*compile-files*`, `*compile-path*`, `*fn-loader*`,
`*unchecked-math*`, `*use-context-classloader*`,
`*warn-on-reflection*`, `add-classpath`, `compile`, `gen-class`,
`method-sig`, and `with-loading-context`.

These names control Clojure compilation, reader evaluation, Java class loading,
or generated JVM classes. Python has materially different import, compilation,
and scope models. Some may gain Basilisp-specific equivalents, but an exact
compatibility promise would be false.

### Clojure and JVM implementation internals

`->Vec`, `->VecNode`, `->VecSeq`, `-cache-protocol-fn`, `-reset-methods`,
`EMPTY-NODE`, `PrintWriter-on`, and `primitives-classnames`.

These expose Clojure's chunked-sequence/vector implementation, Java exception
and printing classes, proxy generation, primitive vector types, or compiler
helpers. They are not stable portability APIs and do not have a direct Python
counterpart.

### Java objects and streams

`resultset-seq`, `stream-into!`, `stream-reduce!`, `stream-seq!`, and
`stream-transduce!`.

The exact APIs require JDBC result sets or `java.util.stream`. Python-native
adapters may be worthwhile under a distinct API, but should not silently
substitute database cursors or streams for those Java types. ``bean``,
``enumeration-seq``, and ``uri?`` now have explicit Python-host contracts for
Python objects, iterators, and parsed URIs.

### Agents and software transactional memory
`sync` is now available as Clojure-compatible transaction syntax:
its flags argument is documented as ignored by Clojure and is likewise ignored
by Basilisp. `io!` is now provided as an explicit transaction side-effect guard,
and agent sends made during a transaction are deferred until it commits.

These names depend on Clojure's agent executor and STM retry/transaction
semantics. Python threads, `asyncio`, and locks can support a useful native
concurrency library, but they cannot truthfully implement Clojure STM by
wrapping the existing atom abstraction. Basilisp now provides executor-backed
`agent`, `send`, `send-off`, `send-via`, error handling, bounded `await-for`,
and Clojure-compatible `await1`. The public executor lifecycle operations and
qualified ``await`` are now available; the dynamic ``*agent*`` action binding
is now also available. Ref history controls retain their Clojure-shaped public
configuration and the requested minimum committed values. Basilisp does not
need JVM-style snapshot queues for transaction correctness because each
optimistic transaction retains its own read value.
`agent-errors` is now available as Clojure's deprecated one-item wrapper around
`agent-error`.
The portable Ref operations ``ref``, ``dosync``, ``alter``, ``ref-set``,
``commute``, and ``ensure`` are now exposed from ``basilisp.core`` after a
shared Clojure/Basilisp conformance fixture. ``ref-history-count``,
``ref-min-history``, and ``ref-max-history`` are also available; retained
minimum history is synchronized with successful commits.
``seque`` is also available with the portable queued-sequence contract: it
accepts a positive buffer size or a queue-like object, preserves realized
values, and ends after a producer error as Clojure's Agent-backed version does.
