# Clojure Core Parity Classification

This document classifies the 143 symbols reported missing by the initial
`core_parity_matrix.py` run on 2026-07-10. The matrix is a raw public-var
comparison, so it includes Clojure implementation details and Java-runtime
facilities in addition to portable user APIs.

The goal is to implement every portable API with tests. Symbols in **Needs
review** must not receive a compatibility-shaped stub: their documented Clojure
behavior depends on the JVM, Clojure's compiler internals, or its STM/agent
runtime. A Basilisp fork needs an explicit Python-native design before exposing
one of those names.

## Implemented

The following twenty-nine symbols are now implemented and no longer appear as
gaps:

`alias`, `array-map`, `bound?`, `comparator`, `create-struct`, `defstruct`,
`line-seq`, `list*`, `locking`, `num`, `partitionv`, `partitionv-all`,
`re-groups`, `re-matcher`, `reductions`, `replicate`, `splitv-at`, `struct`,
`struct-map`, `subseq`, `rsubseq`, `sorted-map`, `sorted-map-by`, `sorted?`,
`sorted-set`, `sorted-set-by`, `test`, `unsigned-bit-shift-right`, and
`xml-seq`.

## Portable Implementation Targets

These symbols have useful public behavior that can be ported without claiming
to reproduce JVM internals. They remain implementation work, not review
deferrals.

- Namespace/runtime: `find-protocol-impl` and `find-protocol-method`.
- Reader helpers: `read+string`.
- Numeric and hash helpers: `hash-combine`, `hash-ordered-coll`,
  `hash-unordered-coll`, and `mix-collection-hash`. Hash helpers must be
  documented as Basilisp hash semantics unless they can be proven byte-for-byte
  compatible with Clojure.

## Needs Review

### Clojure compiler, reader, and Java class-loader state

`*'`, `+'`, `-'`, `*allow-unresolved-vars*`, `*compile-files*`,
`*compile-path*`, `*file*`, `*fn-loader*`, `*math-context*`, `*read-eval*`,
`*reader-resolver*`, `*repl*`, `*source-path*`, `*suppress-read*`,
`*unchecked-math*`, `*use-context-classloader*`, `*verbose-defrecords*`,
`*warn-on-reflection*`, `add-classpath`, `compile`, `definline`, `gen-class`,
`method-sig`, `with-loading-context`, and `with-local-vars`.

These names control Clojure compilation, reader evaluation, Java class loading,
or generated JVM classes. Python has materially different import, compilation,
and scope models. Some may gain Basilisp-specific equivalents, but an exact
compatibility promise would be false.

### Clojure and JVM implementation internals

`->ArrayChunk`, `->Vec`, `->VecNode`, `->VecSeq`, `-cache-protocol-fn`,
`-reset-methods`, `EMPTY-NODE`, `PrintWriter-on`, `StackTraceElement->vec`,
`Throwable->map`, `accessor`, `chunk`, `chunk-append`, `chunk-buffer`,
`chunk-cons`, `chunk-first`, `chunk-next`, `chunk-rest`, `chunked-seq?`,
`primitives-classnames`, `print-ctor`, `print-dup`, `print-method`,
`print-simple`, `proxy-call-with-super`, `proxy-name`,
`seq-to-map-for-destructuring`, and `vector-of`.

These expose Clojure's chunked-sequence/vector implementation, Java exception
and printing classes, proxy generation, primitive vector types, or compiler
helpers. They are not stable portability APIs and do not have a direct Python
counterpart.

### JVM primitive arrays, Java objects, and Java streams

`aset-boolean`, `aset-byte`, `aset-char`, `aset-double`, `aset-float`,
`aset-int`, `aset-long`, `aset-short`, `bean`, `boolean-array`, `byte-array`,
`char-array`, `enumeration-seq`, `resultset-seq`, `stream-into!`,
`stream-reduce!`, `stream-seq!`, `stream-transduce!`, and `uri?`.

The exact APIs require Java primitive arrays, `java.beans`, `Enumeration`, JDBC
result sets, `java.util.stream`, or `java.net.URI`. Python-native adapters may
be worthwhile under a distinct API, but should not silently substitute lists,
iterators, database cursors, or URL parse results for the Java types.

### Agents and software transactional memory

`*agent*`, `agent`, `agent-error`, `agent-errors`, `alter`, `await`,
`await-for`, `await1`, `clear-agent-errors`, `commute`, `dosync`, `ensure`,
`error-handler`, `error-mode`, `io!`, `ref`, `ref-history-count`,
`ref-max-history`, `ref-min-history`, `ref-set`, `release-pending-sends`,
`restart-agent`, `send`, `send-off`, `send-via`, `seque`,
`set-agent-send-executor!`, `set-agent-send-off-executor!`,
`set-error-handler!`, `set-error-mode!`, `shutdown-agents`, and `sync`.

These names depend on Clojure's agent executor and STM retry/transaction
semantics. Python threads, `asyncio`, and locks can support a useful native
concurrency library, but they cannot truthfully implement Clojure STM by
wrapping the existing atom abstraction.

### Version identity and unchecked arithmetic

`*clojure-version*`, `clojure-version`, and `unchecked-remainder-int`.

Reporting a fabricated Clojure version would misstate runtime identity, and
unchecked Java integer arithmetic has fixed-width overflow behavior that
Python integers intentionally do not share. A future fork can define explicit
compatibility metadata and fixed-width numeric operations, but both require a
published policy.
