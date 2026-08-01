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
API is Python-native and awaitable, with explicit buffer, cancellation, close,
timeout, and selection semantics. ``clojure.core.async`` now claims only the
implemented non-``go`` facade subset; ``go``-style code still maps to
``defasync`` and ``await`` until parking semantics are implemented.

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
replace JVM character and writer objects. The public helper boundary follows
Clojure where it is observable: direct ``fresh-line`` fallback behavior,
``write`` option rendering without a trailing ``pprint`` newline, and
``pprint-tab``'s direct-call rejection are covered by shared fixtures, while
tabulation remains an internal formatter service for ``~T``.

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
a shared winner token so a value is neither lost nor delivered twice. ``pipe!``
and ``pipeline!`` now cover the first ordered channel pipeline milestone.
Channel transducers, pub/sub, mult/mix routing, blocking/thread bridges, and a
coroutine-backed ``go`` parking subset are now covered by staged JVM fixtures;
the shipped ``clojure.core.async.impl`` protocol, buffer, channel, and dispatch
source-import surfaces now have Python-native compatibility facades. Deeper
compiler-produced IOC state-machine parity, including direct
``impl.ioc-macros`` semantics, remains later work. See :ref:`core_async_design`
for the staged ``clojure.core.async`` compatibility design.

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

This remains an ``asyncio``-native API: callers may use it from ``defasync``
with ``await``. The ``clojure.core.async`` facade also supports ordinary
synchronous Clojure-shaped construction for task-backed helpers by scheduling
router work on the current event loop or on Basilisp's shared background
channel loop when no loop is running, so blocking consumers such as ``<!!`` can
drain those channels. The facade now exposes a coroutine-backed ``go``/parking
subset for source compatibility. This is not a full Clojure IOC state-machine:
Python coroutines still do not permit an ``await`` to cross an arbitrary
ordinary function boundary. Cross-thread adapters use ``run_coroutine_threadsafe``
only through explicit bridge helpers and must document event-loop ownership.
AnyIO is an optional adapter layer only; it should not become the language
runtime.

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
provides the standard callback and quit semantics. The semantic-depth follow-up
directly covers every audited ``clojure.core.server`` public Var while keeping
live TCP server object identity in local tests. ``repl-read`` uses an explicit
EOF sentinel so EOF exits like Clojure without conflating EOF with the readable
``nil`` form.

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
builtins and dynamically-created objects that lack recoverable source text. The
semantic-depth follow-up covers every audited REPL public Var directly, while
normalizing host-shaped output for documentation/source/tracebacks. ``source``
now reports unresolved symbols like Clojure, ``source-fn`` accepts symbols as
well as Basilisp Vars/Python objects, and ``demunge`` recognizes both Clojure's
standard munged tokens and Basilisp's internal double-underscore tokens.

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
environment, imports Basilisp namespaces, checks that namespace caching
succeeds, and runs the installed ``basilisp`` console script against a temporary
``pyproject.toml``-configured source project. CI runs that artifact probe on
the release-grade Linux/Python 3.14 lane. Only a failing expansion of that probe
justifies a wrapper backend.
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

Standard namespace public-surface auditing is intentionally two-sided.
``scripts/standard_namespace_surface_matrix.py`` fails when a Clojure public Var
is missing from the Basilisp compatibility namespace, and its
``--verify-extensions`` mode also fails when Basilisp-only public Vars drift
from the checked-in extension manifest. This keeps Python-hosted helpers and
explicit extensions available without letting accidental public API changes hide
inside an otherwise green Clojure parity report.

Real-library acceptance is inventory-gated for the same reason. The checked-in
corpus under ``tests/acceptance`` is listed explicitly in
``scripts/library_acceptance.py``. ``--verify-inventory`` fails when a runnable
acceptance library is added or removed without updating that list, so corpus
growth is a reviewed compatibility decision rather than an accidental side
effect of copied source files.

The differential conformance corpus is likewise inventory-gated. The checked-in
``tests/conformance/*_cases.cljc`` files are pinned in
``scripts/differential_conformance.py``. The pREPL fixture now runs inside the
normal full-corpus shard set, so local ``prepl`` and ``io-prepl`` event
contracts are part of the same JVM/Basilisp differential proof as other
standard namespaces. ``--verify-inventory`` fails before sharded execution when
fixture files or their pinned emitted-case counts drift from that manifest,
keeping fixture corpus changes visible in review. After Clojure and Basilisp
outputs match semantically, each checked-in fixture must still emit the
expected number of EDN cases; this prevents accidental loss of proof depth
inside an otherwise conformant fixture file.

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
forms, ``cond``/``case`` pairs, and ``ns``/``require`` declarations. The
dispatch table also covers Clojure's portable hold-first and binding families,
including ``def``/``defonce``, member access forms, ``if``/``if-not``,
``when``/``when-not``, ``condp``, ``with-local-vars``, ``locking``,
``struct``/``struct-map``, and readable ``fn*`` anonymous-function expansions.
It falls back to ordinary list printing for incomplete or unrecognized forms,
including ``try``/``catch``/``finally`` forms that Clojure does not
special-case; golden tests cover the structured forms.

``cl-format`` is implemented as a source-derived portability layer rather
than a wrapper around Python's unrelated ``format`` mini-language. It retains
Clojure's directive parsing and argument-consumption model while adapting
writer handling, characters, and numeric plumbing to Python.

The public print functions use the Clojure-compatible ``print-method`` and
``print-dup`` multimethods. Custom methods receive the active writer and apply
to nested values as well as top-level arguments, while the underlying renderer
continues to enforce ``*print-length*``, ``*print-level*``, and metadata
settings for ordinary collections. Basilisp's root
``*print-namespace-maps*`` value intentionally matches Clojure's default
``true``; callers that need fully qualified keys bind it to ``false``.

The shared differential fixture now covers the portable rendered contract for
ordinary data printing, sorted maps, ``print-table``, stable ``code-dispatch``
definition, ``case``, threading forms, the added formatter-table families, a
deterministic generated code-dispatch corpus across margins, ``cl-format``
numeric/iteration/conditional/plural/newline directives, formatter functions,
custom ``:fill`` logical-block dispatch, combined ``write`` controls, and
radix-prefixed integer/ratio printing. The ``cl-format`` directive layer is
also locked for radix/comma/sign variants, character names, ``~A``/``~S``
padding, justification, recursive ``~?`` indirection, fresh-line boundaries,
standalone ``~_`` rejection, and absolute/relative ``~T`` tabulation. Map
entries and record maps use Clojure's comma separators, ``print-table`` uses
Clojure's vertical outside divider bars, and simple-dispatch numeric rendering
now matches Clojure's non-decimal negative-integer source shape while keeping
ratio denominators unprefixed. The core print-helper fixture separately locks
metadata/readability suppression, print-dup metadata preservation, default and
bound namespace-map rendering, escaped strings, characters, tagged literals,
set truncation, and deterministic generated printable values. ``pprint``
flushes the pretty-writer buffer before writing its trailing newline so
platform line-ending width does not affect object layout; the fixture locks
the formerly divergent exact-margin nested-map case. The exact XP
width-decision follow-up now ports Clojure's recursive section processing and
locks concrete ``condp``/body-form boundary cases, including exact-width
``if``/``when`` predicate/body layouts and ``:fill`` subsection boundaries.

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

``deftype`` and ``reify`` now use declared protocol/interface information to
report inherited method-signature mismatches at analysis time. The check compares
method name, fixed arities excluding ``self``, variadic lower bounds, and
descriptor kind for inspectable instance, class, and static abstract methods.
Warnings include source location and structured expected/actual arity data, and
``^:no-warn-on-arity-mismatch`` suppresses known-safe implementation methods.
The analyzer remains conservative: it does not inspect arbitrary Python
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
shrinking for known portable descriptor and predicate domains and returns
structured pass or failure data. ``checkable-syms`` and
``instrumentable-syms`` report the registered ``fdef`` symbols, ``check``
accepts Clojure-style test.check option maps and target collections, and
``check-fn`` generated-checks an explicit ``fspec`` against a callable or Var.
``with-instrument-disabled`` is a thread-local dynamic validation bypass for
already instrumented calls. Arbitrary predicates still require ``with-gen`` with
an explicit strategy; Hypothesis is an optional test adapter, not the
implementation of the spec contract.

The spec public-surface tranche closes the remaining audited
``clojure.spec.alpha``, ``clojure.spec.test.alpha``, and
``clojure.spec.gen.alpha`` public name gaps. Public protocol/helper names such
as ``Spec``, ``Specize``, ``conform*``, ``explain-data*``, ``specize*``,
``registry``, and the ``*-impl`` constructors are available as compatibility
entrypoints backed by the descriptor engine. ``spec.test.alpha`` exposes
``->sym``, namespace enumeration, discovery, instrumentation, summary, ``check``,
and ``check-fn`` helper names without claiming JVM classpath-wide
instrumentation or Clojure/test.check's JVM-specific shrink result internals.
The semantic-depth tranche for ``spec.alpha`` directly compares portable
contracts across core spec creation, registry lookup, composition,
collections, regex specs, numeric and instant ranges, assertion/explain
behavior, generators, ``fspec``/``exercise-fn``, protocol helpers, and safe
implementation-helper entrypoints. It also locks ``s/abbrev`` to Clojure's
observable symbol/list dequalification behavior. The adversarial follow-up
locks Clojure's chained conformer/unformer behavior for ``s/and``, repeat
backtracking across later regex branches, first-match branch order, ``keys*``
permutation round trips, and tagged regex explain paths, while leaving
JVM-specific internal representation details outside the compatibility claim.
The generator now handles
recursively-defined keyword specs when a nonrecursive base branch is available,
using size-bounded recursion and falling back to base branches at small sizes.
It also generates Clojure-style ``multi-spec`` values by enumerating a
multimethod's registered methods and applying keyword or function retagging to
the generated branch value. ``fspec`` generation now produces invokable values
for descriptors with an ``:args`` spec, validates generated-function calls
against those args, and emits conforming return values from ``:ret`` when
present. The semantic-depth tranche for ``spec.gen.alpha`` directly compares
primitive generators, combinators, lazy generator construction, named/predicate
generator lookup, and property-check result shapes; it also locks in generated
character representation, ``gen/not-empty`` filtering, and persistent-map
iteration for edge keys such as ``##NaN``. The follow-up extends that boundary
through ``s/gen`` named/path overrides, invalid override filtering,
``with-gen`` values embedded in regex specs, and Clojure-style variable repeat
generation for ``s/*`` and ``s/+``. Recursive specs with no base branch and
Python model adapters remain design tasks rather than surface-name tasks.

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
supplies explicit Var wrapping, ``unstrument`` restoration, thread-local
instrument disable scopes, discovery of registered function specs, explicit
``fspec`` checking through ``check-fn``, and bounded generated checks, never
monkey-patching arbitrary Python callables.

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

The semantic-depth follow-up for ``clojure.string`` keeps the Clojure-facing
surface independent from Python convenience helpers. ``split`` follows
Clojure's trailing-empty and positive-limit rules, ``split-lines`` splits only
``\n`` and ``\r\n`` boundaries, ``last-index-of`` treats ``from-index`` as an
inclusive start position, and regex replacement strings use Clojure/Java-style
``$1`` group references and ``re-quote-replacement`` quoting. The Python
interop boundary remains explicit: ``escape`` accepts Python string-keyed maps
without losing non-BMP Python codepoints.

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

The same fixture now exercises transducer completion boundaries directly.
``transduce`` must invoke reducing-function completion even when the input is
empty or reduction has already short-circuited. ``sequence`` must initialize the
transducer once, emit terminal completion output such as ``partition-all``'s
final chunk, preserve normal ``halt-when`` output, and support multi-collection
mapping without treating scalar reduced values as seqable output. Custom
``halt-when`` return functions observe the completed reducing result before
receiving the halting input, and reduced short-circuiting must not run that
completion a second time. Generated fixture rows compare ``sequence``, ``into``,
and ``transduce`` over stateful, filtering, partitioning, and early-terminating
transducer compositions.

The tools.reader follow-up closed the remaining portable public surface for
``clojure.tools.reader``, ``clojure.tools.reader.default-data-readers``,
``clojure.tools.reader.edn``, ``clojure.tools.reader.impl.commons``,
``clojure.tools.reader.impl.errors``, ``clojure.tools.reader.impl.inspect``,
``clojure.tools.reader.impl.utils``, and ``clojure.tools.reader.reader-types``. Reader-type
constructors and coercers create Basilisp's Python-backed stateful readers,
while public character APIs return Basilisp ``Character`` values rather than
one-character strings. Raw positional constructor fields that only affect JVM
implementation details are accepted only to the extent they map to source
position and file metadata. Plain pushback readers are not indexing readers;
only indexing and source-logging reader constructors expose line/column/file
metadata, matching the observed tools.reader boundary. The semantic-depth follow-up exercises root reader
contracts directly: repeated reads and EOF handling, ``read+string`` source
boundaries, regex literals, tagged/default reader bindings, suppressed tagged
literals, reader conditionals, ``read-symbol`` delimiter and source metadata
behavior, ``resolve-symbol`` alias handling, and ``*read-eval*`` enforcement.
The compatibility boundary deliberately emits standard ``clojure.core`` symbols
from ``resolve-symbol`` even though the implementation delegates to
``basilisp.core`` internally. ``tools.reader`` intentionally differs from the
lower-level Basilisp reader default for reader conditionals: source-compatible
``tools.reader/read`` and ``read-string`` reject ``#?``/``#?@`` unless callers
explicitly pass ``:read-cond :allow`` or ``:read-cond :preserve``. The EDN
namespace uses the same stateful reader backend with an EDN mode that allows the
upstream ``inst``/``uuid`` default tags plus caller-provided ``:readers`` and
``:default`` handlers, while rejecting the non-EDN reader macros rejected by
upstream and Basilisp host-extension tags by default. Leading apostrophes in
EDN tokens and metadata are accepted to match ``tools.reader.edn``.
``tools.reader.default-data-readers`` delegates timestamp parsing and validation
to Basilisp's instant implementation: Date-like reads produce timezone-aware UTC
Python datetimes, Calendar-like reads produce Basilisp's offset-preserving
``InstantCalendar`` value, Timestamp-like reads preserve parsed nanoseconds in
``InstantTimestamp``, and UUID reads produce Python ``uuid.UUID`` values. The
JVM namespace's generated ``ThreadLocal`` proxy Var is classified as a
non-portable artifact. ``tools.reader.impl.commons`` is exposed as a portable
source-compatibility namespace for upstream helper callers; its regex,
number-matching, symbol-token parsing, line/comment skipping, and throwing
reader helpers operate over Basilisp's Python-backed reader types while
preserving the observed Clojure return-value boundaries. ``tools.reader.impl.utils``
exposes the adjacent character/predicate, metadata, namespace-key,
``make-var``, ``ex-info?``, ``second'``, version-guard, and ``compile-when``
helpers with the same observed nil/false and macro-expansion boundaries.
``tools.reader.impl.inspect`` exposes the upstream ``inspect``/``inspect*``
surface for portable scalar, string, collection, and truncation rendering.
JVM-specific internal seq class labels, such as vector/map/lazy seq placeholder
names, are treated as host-specific diagnostics rather than portable values.
``tools.reader.impl.errors`` exposes the upstream ``ex-info`` helper surface for
reader errors, EOF errors, illegal-argument errors, and the reader-specific
Unicode, octal, metadata, namespace-map, delimiter, and reader-tag throw
helpers. Error data uses Clojure's portable ``:type :reader-exception`` and
``:ex-kind`` keys, adding ``:file``, ``:line``, and ``:col`` only when the input
reader is indexing-capable.

The tools.logging follow-up closed ``clojure.tools.logging.impl`` public
surface parity, ``clojure.tools.logging.readable`` public surface parity, and
the meaningful root logging Vars. The runtime uses Python's ``logging`` package
as its backend; Java-specific SLF4J, Commons Logging, JUL, and Log4j factory
selectors return ``nil``. The only remaining root-surface delta is an upstream
generated proxy class Var, which is a JVM implementation artifact rather than a
portable logging API.

The standard namespace surface audit is now executable rather than prose-only.
``scripts/standard_namespace_surface_matrix.py`` runs each configured
Clojure/Basilisp namespace pair in one process per runtime, emits a CSV matrix,
and fails when a Clojure public Var is missing from Basilisp without an explicit
classification. The audit intentionally reports Basilisp extensions separately
instead of treating them as parity failures, because many are documented
Python-hosted additions. Its non-portable artifact classification is reserved
for JVM-hosted implementation details that are not portable APIs: currently the
generated ``clojure.tools.logging`` proxy class Var.

Bundled Clojure source resources that intentionally do not create independent
public namespaces are audited by ``scripts/standard_namespace_inventory.py``.
``--verify-source-omissions`` reads the exact resource path from the Clojure
jar, verifies that the file enters its owning namespace with ``in-ns``, requires
the resource namespace, and checks that no independent ``find-ns`` entry is
created. ``--verify-discovered-resources`` separately enumerates
``clojure/*.clj`` and ``clojure/*.cljc`` resources from the active Clojure
runtime jar, normalizes resource paths to namespace names, rejects path-to-name
collisions, and fails on any discovered namespace without a classification.
Together these checks prevent an omitted implementation file or newly added
runtime namespace from silently becoming an unmodeled public namespace in a
future Clojure baseline.

Once a namespace reaches public-surface parity, the next audit layer is direct
semantic fixture coverage. ``scripts/semantic_fixture_coverage.py`` scans shared
``tests/conformance`` fixtures for explicit ``alias/public-var`` calls against
the audited namespace matrix. It is a conservative triage tool, not a proof:
quoted public-surface lists and indirect calls are not counted. Low-coverage
rows should drive future tranches toward behavioral fixtures before more
compatibility shims are added.

``clojure.core`` uses a separate semantic coverage audit because most portable
core usage is unqualified. ``scripts/core_semantic_fixture_coverage.py`` compares
the pinned ``clojure.core``/``basilisp.core`` public sets, then scans the shared
conformance fixtures for explicit qualified core references, ``clojure.core``
aliases, unqualified call heads, and narrow value references for dynamic Vars.
The output is an intentionally conservative weak-coverage map for choosing the
next core behavior tranche. Now that the shared fixture corpus directly covers
all shared public ``clojure.core`` Vars, CI treats this audit as a 100% gate
while still requiring human review before using a low-coverage row as evidence
of an implementation defect.

Full-corpus differential verification must also be reproducible as an
engineering gate, not just as an ad hoc local loop. ``scripts/differential_conformance.py``
therefore supports Basilisp-only ``BASILISP_DO_NOT_CACHE_NAMESPACES=true``
execution and stable modulo fixture sharding. Its default Clojure command pins
the JVM runtime to Clojure 1.12.4 plus the audited contrib dependencies, so
proof output cannot drift with a Clojure CLI default-version change.
Cache-disabled shards are the preferred proof mode when validating broad
namespace parity after many local edits, because they avoid dependence on stale
or oversized ``.lpyc`` artifacts while preserving identical fixture source for
Clojure and Basilisp. CI shards remain one-fixture-per-process so fixture
isolation stays identical to local diagnostic runs; the shard count should be
increased rather than batching fixtures when cache-disabled proof jobs become
too slow.

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
namespace parity. The semantic-depth follow-up directly touches the
Basilisp-only writer protocol and functions under reader conditionals, raising
the audit row to full coverage without treating writers as JVM Clojure APIs.

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

``clojure.test``
~~~~~~~~~~~~~~~~

``basilisp.test`` keeps Basilisp's PyTest integration as a host adapter, but
the Clojure-facing namespace follows ``clojure.test``'s report-driven contract.
Shared fixtures now exercise every audited public Var directly: dynamic test
Vars, ``assert-any``/``assert-predicate`` generated code, custom ``report``
methods, ``inc-report-counter``, ``try-expr``, metadata-backed tests from
``deftest-``/``with-test``/``set-test``, context string helpers, fixture
composition, low-level runner returns, summary runners, and direct
``test-ns-hook`` calls. ``test-vars`` and ``test-all-vars`` are side-effecting
low-level entrypoints that return ``nil`` like Clojure, while ``test-ns``,
``run-test-var``, ``run-test``, ``run-tests``, and ``run-all-tests`` preserve
summary maps for callers. ``compose-fixtures`` and ``join-fixtures`` accept
Clojure-style thunk fixtures; Basilisp's generator-fixture form remains a
``with-fixtures`` extension rather than part of the shared contract. Assertion
forms return Clojure-shaped values after reporting: truthiness and predicate
assertions return their evaluated result, ``thrown?`` returns the caught
exception on success and ``nil`` on failure, ``thrown-with-msg?`` returns the
caught exception after a matching exception type even when the message regex
fails, and equality assertions return the computed boolean for supported public
``=`` arities while preserving Clojure's zero-arity runtime error path through
``try-expr``. Equality assertion report payloads also preserve Clojure's split
between the source ``:expected`` form and the evaluated ``:actual`` form,
including ``(not (= ...))`` for failures. Exception assertion report payloads
also follow Clojure's source-form contract: ``:expected`` is the full assertion
form, no-throw failures report ``nil`` as ``:actual``, wrong exception types are
``:error`` events, and ``thrown-with-msg?`` regex mismatches keep the caught
exception as ``:actual``. ``instance?`` assertion reports follow Clojure's
specialized payload shape by reporting the observed runtime class as
``:actual`` instead of the evaluated predicate form, while generic predicate
failures render the public ``not`` symbol. Fully qualified core predicate heads
such as ``clojure.core/=`` remain generic predicate assertions, matching
Clojure's exact dispatch boundary rather than receiving unqualified special
assertion handling. ``are`` follows Clojure's template-row boundary: empty
binding vectors accept no values, non-empty binding vectors require at least
one full row, and trailing incomplete rows are rejected during macro expansion
instead of being silently ignored.

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

``basilisp.test.junit`` exposes the standard ``clojure.test.junit`` XML reporter
surface. The implementation uses Basilisp's dynamic ``clojure.test/report``
hook, ``*test-out*`` writer, and report counters, while suppressing Basilisp's
human runner output inside ``with-junit-output`` so the XML stream remains
valid. It preserves Clojure's public element helpers and JUnit attribute order,
and escapes assertion text deterministically. Stack traces and source locations
remain Python-hosted.

``core.specs.alpha``
~~~~~~~~~~~~~~~~~~~~

Do not port ``clojure.core.specs.alpha`` as a general application namespace.
Most of its specifications describe Clojure reader, namespace, ``:import``, and
``:gen-class`` grammar, including Java-specific clauses. Basilisp's analyzer is
the authority for its distinct grammar, and a stale public spec layer would
mislead tooling. The one public helper that is portable on its own,
``even-number-of-forms?``, is exposed through ``basilisp.core.specs.alpha`` and
compared against JVM Clojure for ``nil``, sequential, string, map, set, and
seeded vector inputs. Java import, class, and ``gen-class`` specifications
remain omissions rather than weakened copies.

``uuid``
~~~~~~~~

``clojure.uuid`` is a bundled empty namespace. ``basilisp.uuid`` intentionally
has the same empty public surface so source that requires ``clojure.uuid`` can
load without inventing a Python-specific UUID API under a Clojure name.

Java-hosted helper namespaces
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``clojure.java.io``, ``clojure.java.shell``, ``clojure.java.process``, JDBC
helpers, classpath mutation, and Java bean/reflection helpers need individual
classification.
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
Do not extend that exception to Java classloader changes, JDBC result-set
sequences, or Java-bean coercion. Those APIs expose services that Python
already models differently.

``clojure.java.browse`` is a small Python-native UI adapter. Its public surface
matches Clojure's two Vars: ``*open-url-script*`` is an atom with the standard
``:uninitialized`` initial state, and ``browse-url`` launches a configured
script with the URL argument or falls back to Python's ``webbrowser`` module.
``clojure.java.browse-ui`` has no public Vars in Clojure, so
``basilisp.java.browse-ui`` is intentionally empty and exists to preserve the
require path without inventing a Swing replacement.

``clojure.java.javadoc`` is ported as a REPL helper over the browse adapter.
The public Vars ``*feeling-lucky-url*``, ``*feeling-lucky*``,
``*local-javadocs*``, ``*core-java-api*``, and ``*remote-javadocs*`` retain
Clojure's source shape, while ``add-local-javadoc`` and
``add-remote-javadoc`` update Basilisp atoms rather than JVM refs.
``javadoc`` resolves the class of Python values to a Python-style qualified
name, searches configured local/remote prefixes, and delegates the final URL to
``browse-url``. It does not promise JVM ``Class`` module discovery.

``clojure.java.basis`` and ``clojure.java.basis.impl`` are available as small
state facades for Clojure CLI basis-aware tooling. ``init-basis`` is a delay,
``the-basis`` is a delayed atom, and ``update-basis!`` follows Clojure's
``swap!`` shape so portable probes and test harnesses can observe/update the
current basis. Basilisp does not synthesize a Maven/JVM classpath basis; the
default initial basis is ``nil`` unless application code explicitly provides
one.

``clojure.java.classpath`` is available as a Python-hosted classpath
introspection facade. Its public names match ``org.clojure/java.classpath``:
``URLClasspath``, ``urls``, ``get-urls``, ``loader-classpath``,
``system-classpath``, ``classpath``, ``classpath-directories``,
``classpath-jarfiles``, ``jar-file?``, and ``filenames-in-jar``. The portable
contract is classpath shape, protocol dispatch, path/jar filtering, and archive
entry enumeration. Returned entries are Python ``pathlib.Path`` and
``zipfile.ZipFile`` values rather than JVM ``File`` and ``JarFile`` objects,
and the default process classpath is Python's ``sys.path`` rather than
``java.class.path``.

Rewritten standard namespaces must be visible by their requested
``clojure.*`` names after ``require``. Basilisp still loads the backing
``basilisp.*`` implementation module, but the runtime records a global
namespace-name alias so ``find-ns`` and ``ns-publics`` work with source-facing
symbols such as ``clojure.string``, ``clojure.core.server``,
``clojure.stacktrace``, and ``clojure.java.io``. These aliases are lookup
aliases rather than real duplicate namespaces, so ``all-ns`` continues to
report the concrete loaded namespaces.

``clojure.main`` is a special rewrite rather than a plain ``clojure`` to
``basilisp`` prefix replacement. ``basilisp.main`` is Basilisp's Python CLI
module, not a Lisp namespace, so ``clojure.main`` loads
``basilisp.main-compat`` and records the requested Clojure namespace name as
an alias. The compatibility namespace exposes the full Clojure public surface,
delegates portable traceback/name helpers to Basilisp's REPL and stacktrace
libraries, implements the reader sentinel and ``repl-read`` helpers with
``clojure.tools.reader`` pushback readers, supports Clojure's portable
option-driven ``repl`` hooks, and formats deterministic ``:clojure.error/*``
triage maps like Clojure. Actual process entrypoint semantics remain
host-specific: users should invoke Basilisp through its Python CLI rather than
through ``clojure.main/main``. The semantic-depth follow-up directly exercises
every audited public Var, normalizing default namespace names and host exception
classes while proving the portable helper contracts.

``clojure.repl.deps`` is another special rewrite because ``basilisp.repl`` is
already the standard REPL helper namespace. Requires of ``clojure.repl.deps``
load ``basilisp.repl-deps`` and preserve Clojure's three public names:
``add-lib``, ``add-libs``, and ``sync-deps``. The namespace keeps Clojure's
non-REPL guard for deterministic calls, but successful dynamic dependency
loading remains a JVM Clojure CLI capability and raises an explicit
``NotImplementedError`` in Basilisp.

``clojure.tools.deps.interop`` exposes ``invoke-tool`` for source
compatibility. It validates the required tool selector and ``:fn`` symbol using
Clojure-compatible messages, then raises a host-bound error rather than
spawning a Clojure CLI tool inside the Python runtime.

``clojure.inspector`` is provided as a non-graphical inspector model layer.
Clojure's traversal helpers (``collection-tag``, ``is-leaf``, ``get-child``,
and ``get-child-count``) are portable data operations and are implemented
directly. ``tree-model``, ``old-table-model``, ``list-model``, and
``table-model`` return Python-hosted proxy objects with the same Java-style
read methods used by Clojure's Swing models. ``inspect``, ``inspect-tree``, and
``inspect-table`` return those models instead of opening windows, leaving
rendering to Python-native tools.

``clojure.parallel`` is treated as a legacy source-audited namespace rather
than a JVM-verified namespace. The bundled Clojure 1.12.4 source imports
obsolete ``jsr166y`` ForkJoin classes and fails during ``require`` in the
verified baseline. ``basilisp.parallel`` therefore preserves the public
collection API with a sequential operation plan: ``par`` records bounds,
filters, and maps; ``pvec`` realizes them; aggregates and collection-producing
helpers operate over the realized vector. This is compatibility for source and
deterministic data behavior, not a parallel execution contract. The audit is
mechanically enforced by reading ``clojure/parallel.clj`` from the bundled
Clojure source resource, comparing public ``defn`` names against Basilisp's
runtime publics, and by a fixture that checks source-only Clojure boundaries
against executed Basilisp behavior. The adversarial fixture treats operation
composition as the compatibility boundary: indexes remain tied to original
collection positions after ``:bound`` and filters, ``:filter-with``/``:map-with``
read the corresponding element from the companion collection by that position,
and malformed odd trailing operation options are ignored because the legacy
source reduces over ``(partition 2 ops)``. Empty realization, explicit
unsupported operation errors, public arglists, comparator aggregates, and
consecutive duplicate removal are part of the locked contract.

``basilisp.reflect`` exposes Python inspection data behind the portable
reflection entrypoints. ``reflect``, ``type-reflect``, ``typename``,
``do-reflect``, ``Reflector``, and ``TypeReference`` are the shared
Clojure-facing vocabulary. Clojure-shaped ``Method``, ``Field``, and
``Constructor`` records preserve the upstream data keys and factory helper
names, and ``flag-descriptors`` preserves the JVM access flag table as data.
``ClassResolver`` supports callable resolvers. ``JavaReflector`` and
``AsmReflector`` are present as public reflector types for source
compatibility, but ``do-reflect`` on them raises an explicit JVM metadata
boundary instead of inventing Java class metadata from Python objects.
Python-hosted reflection remains available through ``PythonReflector`` and the
default ``reflect`` path. The semantic-depth follow-up directly exercises every
audited public Var in the namespace by separating portable data/protocol
contracts from host-specific reflector behavior: JVM Clojure reflects Java
classes, while Basilisp reflects Python classes through ``PythonReflector``.
The ``clojure.reflect.java`` source resource is treated as implementation code
for ``clojure.reflect`` rather than as a public namespace: plain require is
accepted after ``clojure.reflect`` has loaded, but no separate namespace is
created.

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
checks rather than Java/Python libm last-bit comparisons. The semantic-depth
follow-up directly exercises every audited public Var, including ``expm1``
overflow and small-value behavior, ``tanh`` infinities and signed zero, and
``random`` range/finite constraints. Python's arbitrary precision integers
still mean ``*-exact`` overflow behavior remains documented as host-specific
instead of pretending to reproduce fixed-width JVM arithmetic.

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

``basilisp.test.check`` provides a portable property-testing subset across the
root, ``generators``, ``properties``, ``results``, ``random``, ``rose-tree``,
``clojure-test``, ``impl``, ``clojure-test.assertions``, and empty
``clojure-test.assertions.cljs`` namespaces. Those namespaces are included in
the standard namespace surface matrix against ``org.clojure/test.check``; the
generated JVM ``ThreadLocal`` proxy Var in ``clojure.test.check.random`` is
classified as a non-portable implementation artifact. The compatibility
contract is generator domain shape, combinator behavior, ``quick-check`` result
maps, failure shrinking, the public ``Result`` protocol, result-data keys under
``:clojure.test.check.properties/error``, constructor helpers such as
``->Generator``/``map->Generator``, ``->ErrorResult``/``map->ErrorResult``,
the source-compatible ``->JavaUtilSplittableRandom`` constructor helper, the
public wall-clock millisecond helper, and the assertion bridge's report map
shape. Rose-tree helper behavior for
``collapse``/``seq``/``remove``/``shrink``/``shrink-vector``/``zip``, lazy RNG
state splitting, ratio-producing ``big-ratio`` generation, and portable
``clojure-test`` option/reporting/assertion helpers are covered by shared
fixtures. Exact generated values are not a cross-runtime promise: Basilisp's RNG
is a Python-hosted deterministic splitter, so seeds are reproducible within
Basilisp but not byte-for-byte aligned with Java test.check or Java
``SplittableRandom``. Assertion stack locations are also Python-hosted, so the
portable contract is the public helper and report-data boundary rather than JVM
stack-frame identity.

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

Namespace loading must also remain order independent. Python assigns an
imported submodule to its parent module attribute, so importing
``basilisp.core.memoize`` can otherwise overwrite the parent module's
``memoize`` global used for direct linking to ``basilisp.core/memoize``. The
runtime require path restores an existing parent namespace Var or refer after a
child namespace import; the child module remains importable by its full
``sys.modules`` name, but direct-linked parent Vars keep their Clojure
namespace meaning.

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
gate. The same batch mode supports Basilisp-only namespace-cache disabling and
stable modulo sharding; cache-disabled shards are the preferred proof mode for
source-level library acceptance after broad runtime edits. ``tests/acceptance/portable_library``
is the reference fixture: its ``:clj``/``:lpy`` conditionals perform only
standard namespace substitutions, and its portable source exercises strings,
sets, walking, collections, transducers, exception data, and ``clojure.test``.

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
