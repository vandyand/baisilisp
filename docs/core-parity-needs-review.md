# Clojure Core Parity Classification

This document records the public `clojure.core` parity review trail. The
refreshed `core_parity_matrix.py` run on 2026-07-22 reports 679 shared Vars, 0
missing Basilisp Vars, and 59 Basilisp extensions. The matrix is a raw public-var
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
Clojure's one-chunk-ahead realization behavior. ``range`` now returns a
chunked sequence as well, so lazy transforms over ranges share Clojure's
32-element realization boundary for finite, negative-step, and unbounded
ranges. Zero-step ranges match Clojure's repeating values but remain unchunked.
``*compile-files*``, ``*compile-path*``, and ``compile`` now provide a
Python-native AOT workflow: compilation writes trusted, Python-version-local
``.lpyc`` artifacts below the configured output path, those artifacts can load
without source, and source intentionally wins when both forms are present.
``PrintWriter-on`` now supplies a buffered callback-backed Python text writer
with Clojure's flush/close lifecycle. The deprecated ``add-classpath`` spelling
accepts local paths and ``file:`` URLs, appends them to ``sys.path``, and
invalidates import caches; it deliberately is not a Java classloader façade.
``*warn-on-reflection*`` now captures its binding when compilation begins and
emits a warning for host method or field lookup that Basilisp cannot resolve
from an imported/builtin target. It remains false by default and avoids
executing descriptors while deciding whether a member is statically known.
``stream-reduce!``, ``stream-seq!``, ``stream-transduce!``, and ``stream-into!``
now provide Clojure 1.12's terminal stream operations over Python iterables.
One-shot iterators are consumed exactly once; reduction stops without reading
past a direct ``reduced`` result. ``resultset-seq`` likewise projects a Python
DB-API cursor lazily into fixed keyword-keyed struct maps, lower-cases labels,
and rejects duplicate labels before it reads a row.
``-cache-protocol-fn`` and ``-reset-methods`` now use Basilisp's real
``singledispatch`` protocol backend: cache lookup selects the direct interface
method or a registered host-type extension without invoking it, and reset
clears every method-resolution cache in a protocol. Registration already
invalidates those caches automatically; the public reset hook supports
Clojure-compatible protocol tooling and explicit host type-graph refreshes.
``method-sig`` now projects an inspectable Python host method into Clojure's
three-part reflection shape: its stable name, parameter annotations, and
return annotation. Missing Python annotations are represented by ``nil``;
the callable is never invoked, and uninspectable or anonymous callables fail
explicitly instead of guessing a signature.
``->Vec``, ``->VecNode``, ``->VecSeq``, and ``EMPTY-NODE`` now expose a real
immutable 32-way vector tree. Persistent updates path-copy only the affected
branches, 32-element tails share their unchanged root until promotion, and
the constructor helpers validate their supplied nodes against that tree. The
JVM ArrayManager slot is retained and ignored because vector nodes and tails
are immutable Python tuples.
``with-local-vars`` is also available with thread-local Var-cell semantics.
``*fn-loader*``, ``*unchecked-math*``, ``*use-context-classloader*``,
``primitives-classnames``, ``with-loading-context``, and ``gen-class`` are now
available as compatibility boundaries. The dynamic Vars are bindable and retain
Clojure's defaults; ``primitives-classnames`` exposes Clojure's Java primitive
name table; ``with-loading-context`` evaluates its body; and ``gen-class`` is a
documented no-op macro because Basilisp does not generate JVM class files.

## Portable Implementation Targets

These symbols have useful public behavior that can be ported without claiming
to reproduce JVM internals. They remain implementation work, not review
deferrals.


## Current clojure-test-suite residuals

As of GitHub Actions run `29971832877` on 2026-07-23, the downstream
`basilisp-lang/clojure-test-suite` gate reports `23 failed, 219 passed`.
This is after the scalar text, collection sorting, numeric arithmetic, and
instant epoch arithmetic tranches reduced the suite from `31 failed, 211
passed`.

The remaining failed test files are not all equivalent runtime work. Treat
them as the following queues before changing behavior:

| Failure cluster | Files | Classification | Next action |
| --- | --- | --- | --- |
| Basilisp `:lpy` numeric coercion expectations | `byte`, `double`, `float`, `int`, `long`, `short` | Mostly stale Python-host expectations in the suite, not Clojure parity gaps. The upstream `:lpy` branches still expect behavior such as string coercion and relaxed Python integer bounds in places where Clojure rejects or narrows. | Keep Basilisp aligned with the curated `numeric_coercion_cases.cljc` fixture unless a specific form is proven to differ from JVM Clojure. Patch suite expectations or mark host-extension behavior separately; do not restore permissive Python coercions under Clojure names. |
| Character runtime representation | `char`, `char_qmark`, `string_qmark`, `pr_str`, `prn_str` | Stale suite assumptions from the old char-as-string model. Basilisp now has a distinct `basilisp.lang.character/Character`, so `char?`, `string?`, and printer output are intentionally closer to Clojure. | Preserve distinct characters. Add or maintain conformance fixtures that compare reader, predicate, equality, printing, and string-library behavior against Clojure. Update the upstream suite branch expectations rather than collapsing chars back to strings. |
| Collection operations on characters | `empty_qmark`, `fnext`, `last`, `not_empty`, `remove`, `reverse`, `seq`, `seqable_qmark`, `set` | Secondary fallout from the same char-as-string assumption. The failing `:lpy` branches often treat a character like a one-character string/sequence; Clojure does not. | Do not make `Character` seqable merely to satisfy old `:lpy` tests. Keep collection semantics guarded by `shared_core_semantics_cases.cljc` and `character_cases.cljc`. |
| `subs` Python slicing expectations | `subs` | The suite's `:lpy` expectations use Python slicing behavior for negative, `nil`, and out-of-range indexes. Clojure's `subs` rejects invalid indexes. Basilisp's UTF-16-aware implementation is intentionally Clojure-oriented. | Keep strict Clojure-style index validation and UTF-16 boundaries. If a Python slicing helper is desired, expose it under a Python-native name rather than `clojure.core/subs`. |
| `case` numeric dispatch expectations | `case` | The remaining upstream failures are tied to Python host numeric hash/equality behavior and stale `:lpy` expectations around numeric category dispatch. This area is sensitive because previous work deliberately moved numeric equality toward Clojure's category-aware semantics. A separate portable fixture now covers real `case` dispatch and duplicate-test rejection. | Keep the `case_cases.cljc` fixture as the authority. Do not change numeric dispatch from CI alone unless a new fixture proves a JVM Clojure mismatch. |
| Map-entry coercion through `conj`/`merge` | `conj`, `merge` | Resolved in the parity fork with `merge_cases.cljc`: Basilisp now follows Clojure's observable `merge` reduction-through-`conj` behavior for truthy first arguments while still rejecting invalid map-entry values in map position. The downstream suite's remaining `:lpy` expectations for `(conj {:a 0} '(:b 1))`, `(merge [:foo])`, `(merge :foo)`, and `(merge {} '(:a 1))` are stale relative to JVM Clojure. | Keep the differential fixture as authority. Do not reintroduce the old stricter first-argument guard or arbitrary-list map-entry coercion just to satisfy the stale `:lpy` branches. |

The practical next tranche after the `merge` fix should therefore be **suite
alignment and residual classification**, not broad `.core` mutation. Any new
runtime tranche should first demonstrate one of these residuals is a real JVM
Clojure behavioral gap using a portable differential fixture, not only a failing
`:lpy` branch.

The `run-clojure-test-suite` CI workflow excludes the residual files above via
`scripts/clojure_test_suite_residuals.py`. Each exclusion should remain tied to
an authoritative local differential fixture; removing an exclusion should first
update the external suite expectation or prove a new runtime gap.

## Needs Review

No public `clojure.core` names are currently missing from Basilisp. Future
entries here should be added only when a regenerated matrix or behavioral
fixture demonstrates a new gap.

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
