.. _parity_architecture:

Parity Architecture
===================

This document records the architectural boundaries for the downstream parity
program. It supplements :ref:`parity_roadmap`: the roadmap identifies work,
while this document defines what a credible solution must mean before an API is
advertised as Clojure compatible.

Compatibility Policy
--------------------

Every feature belongs to one of three groups:

* **Compatible** features use a Clojure-facing name only when their public
  behavior is portable and verified against Clojure examples or fixtures.
* **Python-native** features live under ``basilisp.*`` and expose Python runtime
  behavior directly rather than pretending it has JVM semantics.
* **Intentional omissions** remain documented rather than receiving stubs. Java
  class loading, bytecode generation, primitive arrays, JDBC streams, and Clojure
  collection internals fall into this group.

The public-var parity matrix is a discovery tool, not proof of behavior. A
symbol is only considered complete when focused behavior tests and applicable
integration tests cover its contract.

Protocol Metadata
-----------------

Protocols may opt in to ``:extend-via-metadata true``. Dispatch order is:

1. a direct implementation from ``deftype``, ``defrecord``, or ``reify``;
2. an implementation stored in the value's metadata under the fully qualified
   protocol method symbol; and
3. a dynamic implementation supplied by ``extend``, ``extend-type``, or
   ``extend-protocol``.

Only values implementing ``IWithMeta`` participate. Python instance attributes
must not be treated as metadata. Per-value implementations must not be stored
in the type-dispatch cache. ``Datafiable`` and ``Navigable`` use this facility.

Python Concurrency And Channels
-------------------------------

``asyncio`` remains the built-in asynchronous foundation. ``basilisp.concurrent``
owns Python-native tasks, queues, executors, and agent waiting. AnyIO support is
an optional adapter decision, not a replacement runtime.

Channels require a separate compatibility decision. The first public channel
API should be Python-native and awaitable, with explicit buffer, cancellation,
close, timeout, and selection semantics. It should not claim ``core.async``
compatibility until it supports the required operations and documents how
``go``-style code maps to ``defasync`` and ``await``.

Software Transactional Memory
-----------------------------

Refs and ``dosync`` require a purpose-built transaction engine. An external
Python STM dependency is not sufficient unless it provides retrying,
multi-reference atomic commit, conflict detection, side-effect restrictions,
and a compatible licensing and maintenance posture.

The internal ``basilisp.lang.stm`` engine now backs ``basilisp.core/ref`` and
``dosync``. It has versioned references, transaction-local read/write sets,
stable lock ordering, validation at commit, conflict retries, and deterministic
contention coverage. ``io!`` and deferred agent sends are explicit retry-safety
guards. ``commute`` records/replays commutative updates under commit locks, and
``ensure`` opts a Ref back into normal version validation. Ref history controls
retain a configured minimum of committed values and expose Clojure-shaped
minimum, maximum, and count operations without adding a JVM snapshot queue.

Project Configuration And Builds
--------------------------------

``pyproject.toml`` is the project contract. A future ``[tool.basilisp]`` table
will define source roots, test roots, namespace caching, and compiler options.
CLI, REPL, test discovery, and packaging must consume the same resolved model.

PEP 517 is restricted to distribution construction. It must preserve the
existing native-extension build path and must not become a second dependency
resolver. Python tooling remains responsible for dependency resolution.

pREPL And Diagnostics
---------------------

A pREPL implementation requires local-first structured EDN framing,
per-connection namespace and dynamic-binding isolation, output/error capture,
source locations, request identifiers, and explicit Python-object transport.
It should build on shared evaluator and source-map machinery, but it must not
be forced through nREPL's bencode transport.

Compiler source spans, exception formatting, interruptible evaluation, macro
correctness, and closure correctness are prerequisites for claiming a useful
editor protocol. Transcript fixtures should verify pREPL behavior before it is
advertised as compatible.

Standard Libraries
------------------

``basilisp.pprint`` provides ``code-dispatch``, ``:fill`` newlines, and the
portable ``cl-format`` surface. Formatter compatibility is protected with
upstream-derived directive tests; Basilisp character values and Python streams
replace JVM character and writer objects.

``basilisp.spec.alpha`` provides portable validation, conforming, explain-data,
opt-in function-spec instrumentation, and bounded Hypothesis-backed checking.
Broader generator coverage is a later milestone. Python model integrations such
as Pydantic, attrs, and dataclasses belong in adapters rather than replacing
spec semantics.

Clojure Library Portability
---------------------------

There is no general JVM Clojure library loader. Pure ``.cljc`` source with
``:lpy`` reader branches can be supported when its dependencies are portable.
Libraries requiring JAR macros, Java classes, classpaths, or JVM services must
be classified clearly as needing a port or as unsupported. Native Basilisp ports
should be distributed as Python packages.

Milestone Gates
---------------

Each milestone must include:

* a written public contract and explicit non-goals;
* a reproduction or compatibility fixture before implementation;
* focused regression, adversarial, and stress coverage appropriate to its
  concurrency and runtime risk; and
* a documentation update that records any remaining incompatibility.

The recommended execution order is protocol metadata, compiler correctness and
diagnostics, pprint, project configuration, pREPL, native channels, then the
separate STM, spec, and library-portability projects.

Detailed Design Decisions
-------------------------

These decisions resolve the areas where a name-for-name port would otherwise
hide a materially different runtime contract. They are implementation plans,
not claims that the named feature is already available.

Decision Rules
^^^^^^^^^^^^^^

An ambiguous feature is not admitted merely because a package has a similarly
named class. The selected implementation must meet its Clojure-facing contract,
fit Basilisp's supported Python versions and license, and leave a credible
escape hatch for Python-native use. The resulting decisions are:

* STM is an internal runtime facility. No available Python package supplies the
  snapshot, retry, and multi-reference commit semantics that ``Ref`` requires.
  Storage transaction managers may later participate through an adapter, but
  cannot implement ``dosync``.
* Channels are internal ``asyncio`` primitives with a deliberately small,
  awaitable surface. AnyIO is a useful optional bridge, not the runtime, and
  third-party channel packages are reference material rather than dependencies.
* pREPL is a structured evaluator API first and a socket service second. It
  shares evaluation state with nREPL but speaks EDN rather than bencode.
* ``pyproject.toml`` is the one project configuration source. PEP 517 remains
  a distribution hook interface; dependency installation and environment
  selection remain Python-tool responsibilities.
* Reloading is explicit and best-effort. Basilisp can re-execute a module but
  cannot make existing Python references point at its new definitions.
* Spec owns portable validation/conforming behavior. Pydantic, attrs,
  dataclasses, and Hypothesis are adapters and must not define core semantics.
* The printer and compiler are compiler-runtime projects, not dispatch-table
  patches. Their remaining changes require explicit intermediate boundaries:
  printer tokens for ``:fill`` and analyzer phases for macro-producing forms.

Resolution Matrix
^^^^^^^^^^^^^^^^^

The following choices distinguish a compatible surface from an adapter or an
intentional omission. They are the default for new work; changing one requires
an explicit compatibility fixture and migration story.

* **Coordinated mutable state:** implement ``Ref`` and ``dosync`` internally.
  Maintained Python transaction and object-database libraries are useful
  persistence integrations, but not substitutes for in-process multi-Ref
  transactions.
* **Asynchronous message passing:** keep the native channel state machine in
  ``basilisp.concurrent``. Add an AnyIO bridge only as an optional dependency
  after the native contract covers selection and timeout. Do not expose
  third-party stream endpoints as Basilisp channels.
* **Data validation:** implement ``basilisp.spec.alpha`` around portable
  Basilisp values and Clojure-shaped conform/explain data. Model frameworks are
  opt-in boundary adapters: ``datafy`` is the preferred object-to-data hook,
  while model construction remains an explicit application operation.
* **Python model frameworks:** place dataclass, attrs, and Pydantic support in
  optional ``basilisp.contrib`` adapters. Each adapter must expose a lossless
  read projection and a separately named construction/coercion operation; it
  must never register a spec, import a model, or coerce a value implicitly.
* **Packaging and dependencies:** use ``pyproject.toml`` for project settings
  and the selected Python frontend, such as ``uv`` or ``pip``, for environment
  resolution and installation. A future ``add-lib`` may invoke a configured
  frontend in a child process, report the exact environment mutation, and
  require a restart. It must not resolve Maven coordinates or mutate a live
  interpreter's import graph.
* **Reloading:** retain explicit ``:reload`` and ``:reload-all`` behavior over
  Basilisp modules and serialize reload requests with a process-local lock.
  Reload cannot update existing Python object references, instances, closures,
  native extensions, or already imported foreign names.
* **JVM service APIs:** use direct Python facilities under Python-native names:
  ``array``/``memoryview`` for typed binary data, DB-API cursors for result
  iteration, ``urllib.parse`` values for URLs, and Python iterators or async
  iterators for streams. Do not claim Java array, JDBC, URI, bean, or Stream
  compatibility for those adapters.
* **Portable Clojure libraries:** port source and tests into Python
  distributions only when their full transitive dependency graph is portable.
  A port manifest records its upstream revision, substitutions, and deviations;
  Basilisp does not become a Maven/JAR loader.

The sections below record the concrete consequences of those choices, rejected
alternatives, and the gates required before each feature can be advertised.

Transactional Memory
^^^^^^^^^^^^^^^^^^^^^

The public ``stm`` package is not a viable dependency: its last release was in
2013 and it has no declared license. Zope's maintained ``transaction`` package
is a useful transaction coordinator for storage backends, but it does not
provide optimistic snapshots over in-memory refs. Neither supplies Clojure's
``dosync`` semantics.

The implementation is an internal, synchronous optimistic STM in
``basilisp.lang.stm`` with a thin ``basilisp.stm`` extension namespace and a
verified portable surface in ``basilisp.core``.

* A ``Ref`` holds an immutable value, a monotonically increasing version, a
  validator, watches, and a lock. Normal dereference reads the latest committed
  value.
* ``dosync`` is a macro that passes a thunk to the transaction runner. A
  ``contextvars.ContextVar`` makes nested calls in one execution context join
  the outer transaction. A transaction never crosses a thread or process
  boundary; callers must start a separate transaction there.
* A transaction records first-read versions and staged writes. Dereference
  returns a staged value when present; ``alter`` and ``ref-set`` run only
  against that in-transaction value.
* Commit acquires every read/write ref lock in a stable identity order,
  validates every recorded version, validates staged values, installs all
  values, increments versions, and releases locks before running watches.
  A conflict discards the attempt and reruns the thunk. Compatibility mode
  retries until success or user code throws; the experimental namespace may
  expose an explicit attempt/time limit that reports structured conflict data.
* Transactions are synchronous and must not await. Retried bodies make external
  effects unsafe; ``io!`` rejects a dynamically marked impure operation while a
  transaction is active. Agent sends are queued until after commit only.

The current milestone includes ``commute``: it records each operation
separately, returns its in-transaction result, and replays each operation
against the newest committed value under the commit locks. A normal write after
commute is rejected, while a commute after a normal write remains a normal
validated write. ``ensure`` provides optimistic read-protection by retaining
version validation for a Ref that would otherwise be a pure commute; it does
not recreate the JVM's long-held read locks. History tuning and asynchronous
transactions remain excluded. The test gate includes deterministic
barrier-driven conflicts, randomized operation histories checked against a
serialized model, commute/ensure replay interleavings, validator/watch ordering
tests, nested transaction tests, and high-contention stress coverage.
``scripts/stm_contention_probe.py`` records retries, worst-case attempts, and
completion time for a forced-yield multi-thread sample; it is a measurement aid,
not a throughput benchmark or a basis for adding Ref history queues.

This is a compatibility feature, not a general-purpose database transaction
API. The external ``stm`` distribution is unlicensed and unmaintained, and
Zope's ``transaction`` package coordinates storage resource managers rather
than providing a versioned in-memory snapshot. It may later be useful behind a
separate storage adapter, but it must not participate in a ``dosync`` commit
until that adapter can validate and atomically publish with the Ref write set.

The initial engine must reject an attempt to await and report conflicts through
structured exception data when an explicitly configured timeout or attempt
limit stops a retry. Awaiting allows another task to observe speculative
control flow. As with Clojure Refs, host objects are accepted but users must
treat a stored value as immutable: mutation outside a transaction voids
snapshot guarantees and cannot be detected reliably for arbitrary Python
objects. The exception data should identify the transaction, conflicting Ref
identities, and attempt count, so applications can recover without a
fabricated MVCC guarantee. Locks, not an implementation-specific assumption
about the GIL, establish the commit boundary.

Channels And Async Interoperability
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Do not make an external channel package the runtime primitive. ``aiochan`` is
Apache-licensed and a useful semantic reference, but its last release predates
the project's supported Python range. ``cs-queues`` is actively released but
GPLv3-licensed and thread-oriented. An ``asyncio.Queue`` alone is insufficient:
its zero capacity means unbounded rather than rendezvous, and Python versions
supported by Basilisp do not share a uniform close and selection API.

``basilisp.concurrent`` now provides the first channel surface:

* ``chan`` creates a loop-bound, awaitable channel with an explicit buffer
  policy: rendezvous, fixed, sliding, or dropping.
* ``put!``, ``take!``, ``close!``, ``closed?``, ``offer!``, and ``poll!`` are
  the first surface. ``nil`` is rejected on put, preserving Clojure's ability
  to use ``nil`` as the closed-channel take result.
* The implementation owns queues of pending put and take futures. Cancellation
  must remove its waiter atomically, close must wake every waiter, and a fixed
  buffer must apply backpressure without growing.

``alts!`` and ``timeout`` complete the first selection surface. Selection uses
a shared winner token so a value is neither lost nor delivered twice.
Transducers, pipelines, pub/sub, and transducers-on-channels are later work.

``(alts! ports & opts)`` accepts take channels and ``[channel value]`` put
pairs; it returns
``[value port]``, with put values represented by their boolean completion
result. ``:priority true`` attempts ready ports in supplied order. Otherwise,
ready ports must be selected fairly rather than accidentally following deque
order. ``:default value`` returns ``[value :default]`` without registering any
waiter. The internal registration protocol must reserve a single winner before
matching a put or take, deregister every losing waiter, and handle cancellation
and close races. ``timeout`` should be a one-shot channel backed by the owning
event loop's timer and must remove its timer handle when closed early.

This is initially an ``asyncio`` API: callers use it from ``defasync`` with
``await``. A ``go`` macro is explicitly deferred because Python coroutines do
not permit an await to cross an arbitrary ordinary function boundary. Calling
the result ``core.async`` before it offers the documented core operations would
be misleading. Cross-thread adapters may use ``run_coroutine_threadsafe`` but
must be opt-in and must document event-loop ownership. AnyIO is an optional
adapter layer only; it should not become the language runtime.

The test gate includes cancellation while blocked in both directions, close
races, FIFO fairness, every buffer policy, timeout and ``alts!`` races, and
randomized producer/consumer traces checked for loss, duplication, and blocked
waiters after shutdown.

The implementation should not wrap ``asyncio.Queue`` directly. A queue with
``maxsize=0`` is unbounded, whereas a Clojure-style unbuffered channel is a
rendezvous. Queue shutdown is also only available in newer Python versions,
while Basilisp supports Python 3.10. Instead, a channel owns deques of put and
take waiters plus an optional buffer object. Each operation is settled through a
single state transition under the event-loop thread; cancelled futures are
discarded before matching, and close resolves every remaining waiter exactly
once. ``alts!`` must reserve one operation with a shared winner token before
completing its future.

AnyIO's memory object streams are well-maintained and support multiple async
backends, but they expose split send/receive endpoints and their own close and
exception conventions. Provide adapters only after the native contract is
proven. ``aiochan`` is a useful semantic reference but has not released since
2022; the actively released ``cs-queues`` is synchronous and GPLv3. Neither
should become a core dependency.

pREPL
^^^^^

Basilisp now has local ``prepl`` and ``io-prepl`` APIs, alongside the existing
nREPL server. ``basilisp.contrib.repl_session`` owns namespace and history
bindings, compiler execution, namespace transitions, and output/error streams.
pREPL preserves reader source text, tap forwarding, and structured event
serialization; nREPL preserves its bencode batch-result and history protocol.
This removes the duplicated dynamic-binding/compiler path before any remote
server work.

The internal service receives code plus session state and emits ordered events.
Its initial event model is the Clojure pREPL contract:

* exactly one ``{:tag :ret :val ... :ns ... :ms ... :form ...}`` event per
  successfully read form;
* zero or more ``:out`` and ``:err`` events during evaluation;
* ``:exception true`` plus structured Basilisp exception data on evaluation or
  reader failure; and
* explicitly unsupported values represented through a safe printed form rather
  than arbitrary Python object serialization.

``prepl`` operates over supplied readers and callbacks for deterministic tests
and starts in the conventional ``user`` namespace unless an explicit namespace
is supplied. ``io-prepl`` writes one EDN map per line, using ``pr-str`` for
return values.
``server-make`` now adds a loopback-default socket server, one isolated
namespace per connection, newline-delimited EDN framing, bounded incremental
input buffering, and clean shutdown. ``remote-prepl`` is the matching client
adapter for an ``io-prepl`` endpoint: it concurrently forwards text input,
decodes newline-delimited EDN events, and transforms ``:ret``/``:tap`` values
with configurable reader functions. Its bounded event framing, callback-error
envelopes, and concurrent transcript coverage are transport safeguards, not a
network security model. The server remains loopback-only and deliberately
distinct from nREPL's bencode transport. Remaining remote phases are request
identifiers, authentication hooks, cancellation, and CLI exposure.

``basilisp.core.server`` adds Clojure-shaped ownership around that boundary:
``start-server``, ``stop-server``, ``stop-servers``, and ``start-servers``
manage named TCP listeners through an atomic, process-local registry. Its accept
function receives dynamic text-stream bindings and optional configured arguments,
so ``io-prepl`` can serve directly while ordinary text handlers remain possible.
``repl`` also supplies the prompt-oriented protocol from the conventional
``user`` namespace, including REPL helper functions and the shared evaluator's
history and error behavior; ``:repl/quit`` and EOF end a connection. It defaults
to loopback binding and daemon threads, rejects duplicate names without leaking a
bound socket, and accepts Clojure-style EDN property entries. ``repl-read``
cannot reproduce the JVM reader's line-start prompt sentinel, but otherwise
provides the standard callback and quit semantics.

``with-local-vars``
~~~~~~~~~~~~~~~~~~~

``basilisp.core/with-local-vars`` now provides Clojure's small local-mutation
escape hatch without interning temporary names into user namespaces. It creates
dynamic Var cells, installs their initial values as one thread-local binding
frame, and always removes that frame through ``try``/``finally``. Values must be
read and written through ``var-get`` and ``var-set``; nested scopes and
``bound-fn``/Future propagation retain the normal dynamic-binding isolation.

The nREPL adapter also serves ``macroexpand`` requests through the same
namespace-resolution context used by evaluation. It supports one-step, full,
recursive, and next-subform expansion without evaluating client code;
malformed or unsupported requests return terminal protocol errors rather than
ending the connection.

The ``classpath`` operation reports a read-only snapshot of the Python import
search path in place of a JVM classpath. It normalizes empty and relative
entries without importing modules or mutating interpreter state.

Interactive REPL inspection now uses the same portable policy. ``basilisp.repl``
provides deterministic ``apropos``/``dir`` discovery, documentation and source
lookup, identifier ``demunge``, root-cause traceback display, and the remaining
``clojure.repl`` public host-boundary helpers from the live namespace registry.
``set-break-handler!`` adapts Python SIGINT handlers, ``thread-stopper``
returns a handler that raises ``KeyboardInterrupt`` in the calling thread, and
``stack-element-str`` renders Python traceback/frame values. It does not claim
JVM debugger, arbitrary thread-stopping, or Java ``StackTraceElement``
compatibility: those behavior families are host services, not portable Clojure
contracts. Namespace scans are read-only and source lookup is safe for Python
builtins and dynamically-created objects that lack recoverable source text.

The evaluator boundary is a small Python service rather than a network handler:
``evaluate_form(session, form, context, emit) -> outcome``. ``session`` owns
the current namespace and dynamic history; ``emit`` receives only stream text.
``prepl`` supplies reader/source framing and event callbacks, while ``io-prepl``
serializes each event as one EDN value per line. ``remote-prepl`` is a client,
not a public listener: it uses bounded newline framing and leaves
loopback-by-default binding in ``server-make``. Authentication, request
identifiers, cancellation, and any non-loopback listener remain separate
security and protocol work.

This preserves the important pREPL properties: one ``:ret`` event for every
successfully read form, any number of ordered ``:out`` and ``:err`` events,
and a structured exception result rather than a transport failure. Arbitrary
Python objects must never be pickled across the boundary. A return-value
formatter may provide a readable representation, but its event still records
that the underlying value is host-specific.

Evaluation interruption needs a separate contract. Async evaluation can
propagate ``CancelledError`` and must run cleanup in ``finally``. Python cannot
safely terminate arbitrary synchronous code running in a thread. Therefore an
in-process pREPL interrupt is cooperative and may only take effect at defined
safe points; a hard-stop mode must execute the request in a worker process and
discard that process on timeout. This is more honest than a thread-killing API
that can leave locks, Vars, or imports corrupted.

Project Configuration And Packaging
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``pyproject.toml`` is already Basilisp's packaging contract and uses a PEP 517
backend through Maturin. The project configuration feature should extend that
single contract rather than introduce a second dependency resolver.

The first configuration schema is::

   [tool.basilisp]
   source-paths = ["src"]
   test-paths = ["tests"]

   [tool.basilisp.compiler]
   warn-on-arity-mismatch = true

Configuration discovery walks from the requested working directory to the
nearest ``pyproject.toml``. Paths are resolved relative to that file and are
deduplicated before being applied to CLI, REPL, nREPL, and test-runner import
contexts. Explicit CLI flags override configuration; configuration overrides
defaults; environment variables retain their existing role for process-level
overrides. Python 3.10 support requires a conditional ``tomli`` dependency,
because ``tomllib`` is only standard library from Python 3.11.

``basilisp.edn`` may later be accepted as a small compatibility marker with a
strictly limited ``:paths`` surface, but it must not resolve Maven coordinates
or alter Python dependency resolution. Likewise, a self-hosting PEP 517 backend
is a separate project. The existing Maturin backend is now verified by
``scripts/package_probe.py``: it builds a wheel and sdist, asserts
representative ``.lpy`` sources are present, installs each artifact into a clean
environment, imports Basilisp namespaces, and checks that namespace caching
succeeds. Only a failing expansion of that probe justifies a wrapper backend.
An interactive ``add-lib`` must manage an explicitly selected Python environment
and require a restart when imports cannot be made safe; it must not silently
invoke a second package manager in the running process.

Reloading is governed by the same boundary. ``reload`` first invalidates import
caches, then re-executes the requested module through Basilisp's importer. It
reports the exact module set reloaded and never claims to update objects already
held by ``from module import name`` or by Python closures. A future ``reload!``
may calculate an explicit dependency closure from import provenance, but it
must require confirmation for non-Basilisp modules and preserve the old module
if a reload fails. Native extensions, modules with external side effects, and
modules without an import spec are intentionally unsupported.

The project resolver is independently testable as ``resolve_project(cwd)``.
It returns absolute paths and compiler options without modifying ``sys.path``.
The CLI, REPL, nREPL server, and test command apply that resolved model at
their entry points. This prevents test discovery and interactive tools from
interpreting the same project differently. Build-backend integration remains a
separate packaging milestone.

Pretty Printing
^^^^^^^^^^^^^^^

The existing XP-style printer has logical blocks, conditional newline tokens,
``simple-dispatch``, and an opt-in ``code-dispatch``. ``:fill`` newline support
uses a local token look-ahead section: it breaks only when the next element
does not fit and does not force later sibling breaks in the enclosing block.
The writer also tracks an inner break separately so nested logical blocks
correctly influence parent fill decisions. Golden tests cover narrow and wide
margins, nested blocks, reader macros, and default data-printing behavior.

``code-dispatch`` is a separate multimethod layered over the same writer. It
handles generic code lists and symbols, reader macros, definition and binding
forms, ``cond``/``case`` pairs, ``try``/``catch``/``finally`` clauses, and
``ns``/``require`` declarations. The dispatch table also covers Clojure's
portable hold-first and binding families, including ``def``/``defonce``, member
access forms, ``if``/``if-not``, ``when``/``when-not``, ``condp``,
``with-local-vars``, ``locking``, ``struct``/``struct-map``, and readable
``fn*`` anonymous-function expansions. It falls back to ordinary list printing
for incomplete or unrecognized forms; golden tests cover the structured forms.

``cl-format`` is implemented as a source-derived portability layer rather
than a wrapper around Python's unrelated ``format`` mini-language. It retains
Clojure's directive parsing and argument-consumption model while adapting
writer handling, characters, and numeric plumbing to Python.

The public print functions use the Clojure-compatible ``print-method`` and
``print-dup`` multimethods. Custom methods receive the active writer and apply
to nested values as well as top-level arguments, while the underlying renderer
continues to enforce ``*print-length*``, ``*print-level*``, and metadata
settings for ordinary collections.

The shared differential fixture now covers the portable rendered contract for
ordinary data printing, sorted maps, ``print-table``, stable ``code-dispatch``
definition, ``case``, threading forms, the added formatter-table families, a
deterministic generated code-dispatch corpus across margins, ``cl-format``
numeric/iteration/conditional/plural/newline directives, formatter functions,
and custom ``:fill`` logical-block dispatch. Map entries and record maps use
Clojure's comma separators, and ``print-table`` uses Clojure's vertical outside
divider bars. Exact XP width-decision heuristics around deeply nested
``condp``/body forms remain a follow-up and should enter the fixture only as
concrete Clojure/Basilisp mismatches with stable margins.

Compiler Correctness And Diagnostics
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The macro-in-``try`` failure is resolved by a compiler phase boundary: macro
expansion happens before the containing compilation unit executes, so a late
runtime binding is insufficient. While analyzing a sequential body, the
compiler now compiles and installs each statement-position ``defmacro`` before
expanding the following form. The original definition remains in the generated
AST and executes in source order at runtime. This applies consistently to
``try``, ``catch``, ``finally``, and the other bodies built through the shared
analyzer helper; cache-loading coverage verifies the same result for compiled
namespaces.

``loop`` closure capture is completed locally and locked by a portable
differential fixture. A function created before ``recur`` closes over that
iteration's values, while a later iteration receives fresh rebound local names.
The fixture covers one and multiple loop locals, let locals derived from loop
state, nested closures, lazy realization after loop exit, a large loop that
does not grow the Python stack, and a seeded closure corpus.

``deftype`` and ``reify`` have enough declared protocol/interface information
to report method-signature mismatches at analysis time. The check should compare
method name, fixed arities excluding ``self``, and variadic lower bounds;
inherited interface methods must be included. It should initially emit an
opt-in compiler warning with source location and expected/actual arities, with
an explicit metadata suppression key. It must not inspect arbitrary Python
callables or claim signature certainty where Python permits dynamic calls.

Finally, structured compiler diagnostics should be the common format for CLI,
nREPL, pREPL, and custom tracebacks: phase, message, source, line, column,
form, cause chain, and a filtered Basilisp frame list. Human rendering is a
presentation layer. This gives editor protocols stable data while retaining a
verbose Python traceback switch for compiler development.

The phase boundary should be a narrowly scoped ``compile-time def`` mechanism,
not execution of arbitrary forms during analysis. In a sequential form such as
``do`` or a ``try`` body, analyze a local ``defmacro``; compile and install its
macro value; then expand the following form in the newly extended macro
environment. The generated runtime form remains in source order, so normal
execution and exception behavior do not move. The design must reject a macro
definition whose initializer depends on a local runtime binding, and it must
roll back the temporary macro environment if analysis of the enclosing unit
fails.

Diagnostics should use a serializable ``CompilerDiagnostic`` record before
adding more output switches. Its required fields are severity, phase, message,
source name, line, column, form data or printed form, and a causal chain. CLI
text, Sphinx examples, nREPL, pREPL, and an eventual editor integration then
become renderers of the same facts instead of separately parsed tracebacks.

Spec And Python Interoperability
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``basilisp.spec.alpha`` now provides pure value validation, conforming, and
explain-data for ``s/def``, ``valid?``, ``conform``, ``unform``, ``and``,
``or``, ``nilable``, ``coll-of``, ``map-of``, ``keys``, ``tuple``, and
``multi-spec``. Its portable sequence grammar now includes ``cat``, ``alt``,
``*``, ``+``, ``?``, ``&``, and ``keys*`` with full-input conformance and
unforming. ``s/keys`` records the data key separately from the registered spec
key, so ``:req-un`` and ``:opt-un`` require unqualified map keys while
validating values through their qualified specs.
Explain data is a stable Basilisp data structure before human-readable
explanation is added. ``fspec``/``fdef`` descriptors and Var-only
instrumentation validate ``:args``, ``:ret``, and ``:fn`` at an explicit call
boundary; they do not patch arbitrary Python callables or existing references
to an original callable. ``basilisp.spec.test.alpha/check`` uses Hypothesis
shrinking for known portable descriptor domains and returns structured pass or
failure data. Arbitrary predicates require ``with-gen`` with an explicit
strategy; Hypothesis is an optional test adapter, not the implementation of the
spec contract.

The spec public-surface tranche closes the remaining audited
``clojure.spec.alpha``, ``clojure.spec.test.alpha``, and
``clojure.spec.gen.alpha`` public name gaps. Public protocol/helper names such
as ``Spec``, ``Specize``, ``conform*``, ``explain-data*``, ``specize*``,
``registry``, and the ``*-impl`` constructors are available as compatibility
entrypoints backed by the descriptor engine. ``spec.test.alpha`` exposes
``->sym``, namespace enumeration, summary, and instrumentability helper names
without claiming JVM classpath-wide instrumentation. The generator now handles
recursively-defined keyword specs when a nonrecursive base branch is available,
using size-bounded recursion and falling back to base branches at small sizes.
It also generates Clojure-style ``multi-spec`` values by enumerating a
multimethod's registered methods and applying keyword or function retagging to
the generated branch value. ``fspec`` generation now produces invokable values
for descriptors with an ``:args`` spec, validates generated-function calls
against those args, and emits conforming return values from ``:ret`` when
present. Recursive specs with no base branch and Python model adapters remain
design tasks rather than surface-name tasks.

Python interoperability should remain direct rather than imitate Java
interoperability. The next native layer should add narrow, explicit adapters for
dataclasses, ``attrs``, Pydantic models, mappings, sequences, and asynchronous
iterables. Each adapter must state conversion direction, metadata policy,
validation/error representation, and whether it copies or views data. Python
type hints can enrich generated call boundaries only when they are declarative;
they must never cause runtime imports or change dynamic dispatch. JVM-only
facilities such as ``gen-class``, Java classloader mutation, Java beans, JDBC streams,
and primitive arrays remain intentional omissions rather than aliases for
unrelated Python types.

The first internal representation should be immutable descriptors plus a
``conform(value, path, via, in_)`` protocol. Every failure returns the same
invalid sentinel internally and collects problem maps only when requested.
That makes ``valid?`` cheap while preserving Clojure's explain-data shape:
``:path``, ``:pred``, ``:val``, ``:via``, and ``:in``. The registry is a
namespaced-keyword-to-descriptor map, and ``s/def`` changes only that registry.
No Pydantic model, Python annotation, or dataclass may implicitly register a
spec.

Dataclass, attrs, and Pydantic adapters should be opt-in constructors that
produce a regular spec and retain conversion details in metadata. They need
separate policies for aliases, defaults, unknown fields, coercion, and error
translation. Hypothesis belongs in ``basilisp.spec.test`` as an optional
generator adapter after descriptors are stable; it must not decide what
``conform`` or ``explain-data`` means. ``basilisp.spec.test.alpha`` now
supplies explicit Var wrapping, ``unstrument`` restoration, and bounded
generated checks, never monkey-patching arbitrary Python callables.

The adapter policy is deliberately conservative because the three model systems
do not mean the same thing by validation. Dataclasses primarily describe field
layout, attrs can run converters before validators, and Pydantic may parse and
coerce values. Therefore an adapter's default read path must produce ordinary
Basilisp data without validation side effects. Its construction path must make
coercion explicit, preserve field aliases and defaults in metadata, and convert
framework validation failures into ordinary, documented problem data rather
than pretending they are native spec failures. ``basilisp.contrib.dataclasses``
now provides that first explicit adapter: a shallow keyword-keyed projection
with provenance metadata and a separately named, non-coercing ``from-data``
constructor. It does not register specs or alter ``datafy`` dispatch. attrs and
Pydantic follow as isolated contrib packages with contract fixtures.

Python interop should similarly prefer narrow vocabulary over Java-shaped
aliases. Add adapters for mappings, sequences, asynchronous iterables, and
model objects only where conversion direction, copying behavior, and error data
are documented. For typed binary data, use a separate Python-native
``memoryview``/``array`` adapter rather than claiming Java primitive-array
compatibility. ``resultset-seq`` is the deliberately narrow exception: it
adapts only DB-API cursors through their ``description`` and ``fetchone``
contract, lower-cases labels, and rejects duplicates. ``uri?`` is similarly
defined against parsed Python URIs rather than Java URL classes.

Remaining Standard Namespace Decisions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The remaining standard namespaces split into small portable contracts and
JVM-hosted contracts. They should not all be treated as equally valuable
"missing namespaces." The following decisions define what a credible next
implementation would contain.

A public-surface audit on 2026-07-23 closed the remaining small portable gaps
in already-ported standard namespaces: ``clojure.string`` now has no missing
Clojure public vars, and ``clojure.data.priority-map`` exactly matches the
upstream public names, including ``trim-newline``,
``->PersistentPriorityMap``, and ``apply-keyfn``. The follow-up host-boundary
audit closed the ``clojure.repl`` and ``clojure.xml`` public-surface deltas with
Python-native adaptations instead of JVM object emulation. Remaining standard
namespace work should now be chosen from semantic-depth failures, missing
third-party-library facades, and explicitly Java-hosted namespaces rather than
simple public-name gaps in the audited set.

The same audit also closed the portable constructor/protocol layer for
``clojure.core.cache``, ``clojure.core.memoize``,
``clojure.core.protocols``, and ``clojure.core.reducers``. The first three now
have no missing upstream public names; remaining extras are Basilisp's explicit
Python class/protocol aliases. ``basilisp.core.reducers`` now exists so the
standard ``clojure.core.reducers`` require path works, with an exact public
surface. JVM-specific cache soft references and reducers ForkJoin hooks resolve
as documented unsupported boundaries rather than silently changing semantics.
Core semantic follow-ups should be proven by differential fixtures instead of
raw downstream-suite failures. ``merge`` now follows Clojure's observable
reduction-through-``conj`` behavior for truthy first arguments, including lists,
vectors, scalars, and map entries. Map ``conj`` still accepts maps, map entries,
nil, and vector-like pairs, but rejects arbitrary sequential pairs such as lists
and strings to match Clojure's map-entry boundary.

The tools.reader follow-up closed the remaining portable public surface for
``clojure.tools.reader`` and ``clojure.tools.reader.reader-types``. Reader-type
constructors and coercers create Basilisp's Python-backed stateful readers,
while public character APIs return Basilisp ``Character`` values rather than
one-character strings. Raw positional constructor fields that only affect JVM
implementation details are accepted only to the extent they map to source
position and file metadata.

The tools.logging follow-up closed ``clojure.tools.logging.impl`` public
surface parity and the meaningful root logging Vars. The runtime uses Python's
``logging`` package as its backend; Java-specific SLF4J, Commons Logging, JUL,
and Log4j factory selectors return ``nil``. The only remaining root-surface
delta is an upstream generated proxy class Var, which is a JVM implementation
artifact rather than a portable logging API.

``datafy``
~~~~~~~~~~

``basilisp.datafy`` exposes the portable ``clojure.datafy`` surface over
``basilisp.core.protocols/Datafiable`` and ``Navigable``. Custom
``datafy`` implementations that return a distinct metadata-capable value keep
their existing metadata and gain the Clojure keys
``:clojure.datafy/obj`` and ``:clojure.datafy/class``. The object value is the
original Basilisp/Python-hosted object and the class value is a stable
Basilisp class symbol rather than a JVM ``Class`` object, so portable fixtures
compare presence and identity rather than host-specific rendering.

``nav`` delegates through ``Navigable`` for custom values and otherwise
returns the supplied value for ordinary non-``nil`` collections. ``nil`` is an
explicit rejection boundary, matching Clojure's lack of a ``nil`` Navigable
implementation.

``edn``
~~~~~~~

``basilisp.edn`` exposes the ``clojure.edn`` reader surface through
``read`` and ``read-string``. Its compatibility boundary is data, not host
reader classes: strings, pushback streams, EOF options, comments, discard
forms, numbers, symbols, keywords, characters, maps, sets, vectors, lists,
namespaced maps, reader constants, custom readers, default readers, and tagged
``#inst``/``#uuid`` forms are compared against JVM Clojure by shared fixtures.
Malformed numbers, duplicate map/set entries, invalid keywords, unclosed
strings, bad escapes, unknown tags, and malformed built-in tags remain rejection
boundaries. ``write`` and ``write-string`` are Basilisp extensions for emitting
the EDN subset and are covered by local round-trip tests rather than Clojure
namespace parity.

``instant``
~~~~~~~~~~~

``basilisp.instant`` is a Python-native namespace, not an alias for
``java.util.Date``, ``Calendar``, or ``java.sql.Timestamp``. Its core
``parse-timestamp`` implements Clojure's documented partial-timestamp grammar:
a year is required, trailing date/time components are optional, and a missing
offset means UTC. The parser passes the ten integer components (year through
offset minutes) to a caller-supplied constructor, making the grammar
independently testable. ``read-instant`` constructs an aware Python
``datetime.datetime`` normalized to UTC. ``read-instant-date`` returns the same
UTC-normalized Date-like value, ``read-instant-timestamp`` returns a UTC
``datetime`` subclass which carries the parsed nanosecond field, and
``read-instant-calendar`` returns a small immutable calendar value preserving
the original offset and local calendar fields.

The ``#inst`` reader now uses the same parser, so partial timestamps, offsets,
and long fractional seconds follow the shared Clojure/Basilisp fixture. Python
datetimes retain microsecond precision, so fractions finer than six decimal
places are truncated after parsing nanosecond components. Leap seconds remain
rejected rather than silently normalized because Python has no representable
leap-second ``datetime`` value. ``datetime`` and the standard library are
sufficient; ``python-dateutil`` would broaden parsing behavior beyond
Clojure's grammar and must not become a required dependency.

``core.reducers``
~~~~~~~~~~~~~~~~~

Basilisp already has serial ``reduce``, transducers, ``eduction``, and custom
reduction protocols. ``basilisp.core.reducers`` now supplies the standard
``clojure.core.reducers`` import path, backed by ``basilisp.reducers``, without
becoming a second general collection API: deterministic
``reducer``/``folder`` and ``fold``, plus ``map``, ``filter``, ``remove``,
``take``, ``drop``, ``mapcat``, ``flatten``, and ``cat``. It preserves
``reduced`` short-circuiting, raw map key/value reduction, and the supplied
combining function's zero-argument identity. The Clojure-compatible boundary is
intentional: bare ``r/reduce`` and ``r/fold`` over maps use key/value reducing
arity, while reducer/folder transformations consumed by serial reduction see
ordinary map entries.

Parallel folding is a separate, opt-in execution policy. Threads do not make
CPU-bound Python reduction parallel under the GIL; process pools impose
pickling, importability, cancellation, exception, and data-copy constraints.
Therefore ``basilisp.core.reducers/fold`` is serial. ``pool`` and ``fjtask`` are
JVM ForkJoin boundaries and raise explicitly when used. A later ``:executor`` option may
accept an application-owned executor only when the collection and reducing
functions pass an explicit portability check. It must neither create global
worker pools nor promise speedup. The implementation remains internal and
protocol-based; no third-party package supplies Clojure's fold/reduced contract.

``test.tap`` and ``test.junit``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``basilisp.test.tap`` now supplies the five Clojure TAP operations (plan, pass,
fail, diagnostic, and ``with-tap-output``). Its report binding emits
Clojure-compatible ``ok``/``not ok`` assertion lines, ``#`` diagnostics, and a
plan through ``basilisp.test/*test-out*``, matching Clojure's
``with-test-out`` capture boundary. ``print-diagnostics`` is public and emits
the same expected/actual lines for passing and failing assertion events. The
basic diagnostics format requires no dependency; YAML diagnostics are an
optional later enhancement.

The Basilisp test runner now routes summaries, uncaught test errors, hook
errors, and fixture failures through the same ``report`` dispatch as
assertions. The default report handler keeps the human renderer, while the TAP
handler owns all output during ``with-tap-output`` so no human text contaminates
the stream and every reported failure is included in the plan. Shared
Clojure/Basilisp fixtures lock the public surface, direct printers,
``print-diagnostics``, ``tap-report`` output, ``with-tap-output`` binding, and a
seeded diagnostics corpus; ``tap.py`` and ``pytest-tap`` remain useful
interoperability checks rather than dependencies.

``clojure.test.junit`` is intentionally omitted. Its contract is tied to JUnit
classes and XML/reporting conventions already covered by Python test runners.
Pytest's JUnit XML option and ``unittest`` are host-level integrations, so a
Basilisp alias would add a familiar name without compatible behavior.

``core.specs.alpha``
~~~~~~~~~~~~~~~~~~~~

Do not port ``clojure.core.specs.alpha`` as a general application namespace.
Its specifications describe Clojure reader, namespace, ``:import``, and
``:gen-class`` grammar, including Java-specific clauses. Basilisp's analyzer is
the authority for its distinct grammar, and a stale public spec layer would
mislead tooling. Extract reusable predicates only where they are meaningful to
the Basilisp compiler, beginning with even binding forms, function declarations,
destructuring, and ``ns`` clauses. Keep them in a private analyzer schema module
until external tools need a stable, versioned diagnostics schema. Java import,
class, and ``gen-class`` specifications remain omissions rather than weakened
copies.

Java-hosted helper namespaces
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``clojure.java.io``, ``clojure.java.shell``, ``clojure.java.process``,
``clojure.java.browse``, ``clojure.java.javadoc``, JDBC helpers, classpath
mutation, and Java bean/reflection helpers need individual classification.
Existing ``basilisp.io``, ``shell``, ``process``, ``reflect``, and ``url``
namespaces are Python-native ports where their data contract is useful. Further
work should extend those namespaces with standard-library values such as
``pathlib.Path``, ``subprocess.CompletedProcess``, ``urllib.parse`` results,
and Python inspection data. ``basilisp.java.shell`` exposes the full
``clojure.java.shell`` public surface, including ``*sh-dir*``, ``*sh-env*``,
``with-sh-dir``, and ``with-sh-env``; its shared fixture locks result maps,
stdin, environment override/binding, directory binding, byte output, and seeded
commands. ``basilisp.java.process`` is the deliberately narrow exception to the
alias rule: its Clojure 1.12 process surface maps cleanly to
``subprocess.Popen`` and is therefore available through the automatic
``clojure.java.process`` alias, with documented Python stream and Future values.
The alias exports only Clojure's public names; Basilisp-only helpers such as
``communicate`` remain on ``basilisp.process``. A shared conformance fixture
locks the public surface, captured stdout, environment replacement/merge,
``exit-ref`` timeout behavior, ``io-task`` dynamic binding capture, and a seeded
``exec`` corpus.
Do not extend that exception to Java classloader changes, JDBC result-set sequences,
browser/Javadoc wrappers, or Java-bean coercion. Those APIs expose services that
Python already models differently.

``basilisp.xml`` is a deliberately small data-oriented XML adapter and is
available through the usual ``clojure.xml`` import-path alias. It translates
documents to immutable ``xml/element`` struct maps, preserves mixed content,
omits whitespace-only text nodes, and emits deterministic attribute order.
``tag``, ``attrs``, and ``content`` are real struct accessors, and the remaining
``clojure.xml`` SAX public names are present as Python-host boundary adapters:
``sax-parser`` creates a Python SAX parser, ``disable-external-entities`` applies
supported SAX safety flags, and ``startparse-sax``/``startparse-sax-safe`` feed
the same bounded immutable-tree parser used by ``parse``. Its first boundary is
intentionally narrow: only unqualified ASCII XML names are accepted;
namespace-qualified names, DTDs, and entity declarations are rejected; and input
is bounded to 4 MiB by default. ElementTree cannot preserve lexical prefix
choices, so this adapter does not promise namespace, prefix, byte, or streaming
round trips. A shared Clojure/Basilisp conformance fixture locks the public
surface, struct accessors, second-arity parse path, accepted parse subset,
attributes, nested elements, mixed text, whitespace/comment omission, built-in
XML entity decoding, malformed-input errors, and a seeded element corpus.

``basilisp.data.csv`` exposes the small portable ``clojure.data.csv`` contract
through the normal import-path alias. It retains lazy row reading and Clojure's
separator, quote, quote-predicate, and explicit LF/CRLF emission options, using
Python text streams and the standard CSV parser. Java Reader/Writer object
compatibility and arbitrary dialect options remain host-specific rather than
part of the advertised surface.

``basilisp.math`` exposes the ``clojure.math`` public surface through a
Python-hosted implementation that preserves Clojure's floating-point domain
categories, signed zero behavior, rounding, exponent, next-value, and ordinary
exact-integer results. A shared conformance fixture uses category and identity
checks rather than Java/Python libm last-bit comparisons. Python's arbitrary
precision integers still mean ``*-exact`` overflow behavior remains documented
as host-specific instead of pretending to reproduce fixed-width JVM arithmetic.

``basilisp.core.rrb-vector`` provides the portable public
``clojure.core.rrb-vector`` constructors, concatenation, and slicing API over
Basilisp's ordinary persistent vectors. The compatibility target is the
functional result, vector-ness, arity/rejection boundary, and observable
metadata behavior: one-arity ``catvec`` preserves its input metadata,
multi-vector ``catvec`` keeps the left metadata when the left side contributes
elements, empty-left concatenation follows the right vector's metadata, and
``subvec`` preserves source vector metadata. Basilisp does not emulate the JVM
RRB tree layout or expose internal node/view classes.

``basilisp.set`` follows ``clojure.set``'s functional collection contract while
retaining Basilisp-only extension helpers such as ``disjoint?`` and
``symmetric-difference``. ``union`` has Clojure's zero-arity identity, while
``intersection`` and ``difference`` keep Clojure's zero-arity rejection
boundary. ``union``, ``intersection``, ``difference``, and ``select`` rebuild
through ordinary persistent collection operations so metadata and sorted set
behavior come from the same backing set Clojure would select. Natural joins
return ``#{}`` for empty relations and use the keys shared by the first row of
each non-empty relation, not the keys common to every row.

``basilisp.template`` preserves ``clojure.template``'s data-walking replacement
model. ``apply-template`` builds the binding map with Clojure's ordinary
last-write-wins map semantics, tolerates short and long value lists, and walks
quoted forms as data. ``do-template`` expands to a ``do`` over complete
argument groups and drops incomplete trailing groups, matching Clojure's
``partition``-based behavior. The Clojure zero-binding case is pathological and
is not a compatibility target.

``basilisp.walk`` is a direct port of ``clojure.walk``'s recursive traversal
contract. Lists, sequences, vectors, map entries, maps, sets, records, and
scalars keep the same traversal points as Clojure, while Basilisp exposes the
``IWalkable`` extension protocol as an implementation hook. Map and set
reconstruction follows Clojure's ``empty``/``into`` shape, so walking a sorted
map or sorted set preserves sorted behavior and metadata rather than degrading
to hash collections. Shared fixtures compare replacement helpers, key
transforms, traversal order, macro expansion, metadata, sorted collections, and
a generated nested-data corpus against JVM Clojure.

``basilisp.zip`` is a direct functional-zipper port rather than a Python tree
adapter. Locations remain immutable vectors carrying path metadata, and the
public behavior is the Clojure navigation/editing contract: depth-first
``next``/``prev``, sibling navigation, insertion, replacement, removal, root
reconstruction, and custom constructor functions. Shared fixtures compare
navigation summaries and generated traversal/edit/removal corpora against JVM
Clojure. ``seq-zip`` preserves Clojure's edge behavior when removing the only
child of a sequence root: rebuilding with nil children is an error boundary, not
a silent nil root.

``basilisp.tools.macro`` provides the portable ``clojure.tools.macro`` API for
``macrolet``, symbol macros, templates, recursive macro expansion, and
``name-with-attributes``. Shared fixtures compare deterministic expansions,
lexical binding protection, global symbol macro evaluation, template results,
qualified local-name rejection, and generated symbol-macro forms against JVM
Clojure. Exact ``mexpand-all`` output for macros such as ``for`` remains a
compiler-host boundary: Clojure prints JVM lazy-seq internals and generated
symbols, while Basilisp may preserve source-shaped forms to avoid recursively
rewriting compiler-generated ``recur`` state machines outside analyzer scope.

Library Portability
^^^^^^^^^^^^^^^^^^^

Portable source is a source-level question, not a dependency-coordinate
question. A candidate Clojure library must have ``.cljc`` or otherwise portable
source, a ``:lpy`` reader path where host behavior differs, no required JVM
macros or classes, and dependencies that have the same classification. The
fork should publish a small manifest per port recording upstream revision,
reader features, substitutions, tests run, and remaining deviations. A Python
distribution containing the port is the deployment unit; no JAR loader or
Maven resolver belongs in the Basilisp runtime.

The practical porting workflow is: prove a library's source and transitive
dependencies portable; add the smallest ``:lpy`` reader branches necessary;
port upstream tests before behavior changes; and publish the result as a Python
package with a machine-readable manifest. The manifest records upstream tag and
commit, source checksum, reader-feature substitutions, test command, supported
Python versions, and known deviations. This is more maintainable than a central
claim that a changing Maven ecosystem can be loaded at runtime.

``scripts/portability_manifest.py`` creates the initial JSON manifest from a
source tree without fetching dependencies or executing code. It records every
``.clj``, ``.cljc``, and ``.lpy`` file with its checksum, reader features,
requires, and blockers. A tree is classified as ``portable``,
``needs-lpy-port``, or ``jvm-only``; the latter two states require a reviewed
port or explicit omission before publication.

``scripts/library_acceptance.py`` turns that static evidence into an execution
proof for a multi-file source tree. It validates the checked-in manifest, runs
the library's ``run.cljc`` entrypoint under both Clojure and Basilisp, and
compares the final EDN test summary while allowing test frameworks' preceding
human-readable output. Its ``--all`` mode discovers every checked-in
``run.cljc`` with a portability manifest below ``tests/acceptance`` and runs
them in stable order, so upstream acceptance additions share one reviewable
gate. ``tests/acceptance/portable_library`` is the reference
fixture: its ``:clj``/``:lpy`` conditionals perform only standard namespace
substitutions, and its portable source exercises strings, sets, walking,
collections, transducers, exception data, and ``clojure.test``.

An upstream acceptance directory may provide ``acceptance.json`` to record the
pinned upstream URL and revision plus the exact standard-namespace
substitutions used by its adapters. The first admitted upstream snapshot is
``cognitect-labs/anomalies``: its unchanged ``.cljc`` source is pinned as a Git
submodule and its public anomaly spec is proved under Clojure and Basilisp via
the explicit ``clojure.spec.alpha -> basilisp.spec.alpha`` substitution.

Libraries that are primarily useful abstractions but depend on Java services
should receive a native Basilisp implementation only when their public contract
is valuable independently of the JVM. Otherwise, document the missing runtime
service and point users to the appropriate Python library. This distinction
keeps the fork from accumulating compatibility names whose behavior surprises
both Clojure and Python users.
