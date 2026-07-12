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

``basilisp.stm`` precedes ``basilisp.core/ref``. Its first implementation has
versioned references, transaction-local read/write sets, stable lock ordering,
validation at commit, conflict retries, and deterministic contention coverage.
``commute``, history controls, deferred agent sends, and ``io!`` follow only
after that base contract gains broader state-machine coverage.

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

``basilisp.pprint`` should gain ``code-dispatch`` and ``:fill`` newlines using
golden output fixtures covering metadata, nesting, widths, print level, and
print length. ``cl-format`` is a separate formatting-language project and is
not bundled into that milestone.

``basilisp.spec.alpha`` should begin with portable validation, conforming, and
explain-data behavior. Function instrumentation and generator support are later
milestones. Python model integrations such as Pydantic, attrs, and dataclasses
belong in adapters rather than replacing spec semantics.

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

The right first implementation is an internal, synchronous optimistic STM in
``basilisp.lang.stm`` with a thin ``basilisp.stm`` public namespace. It should
not add ``ref`` to ``basilisp.core`` until its compatibility contract holds.

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
  effects unsafe; ``io!`` should reject a dynamically marked impure operation
  while a transaction is active. Deferred agent sends belong after commit only.

The first milestone intentionally excludes ``commute``, history tuning,
``ensure``, and asynchronous transactions. ``commute`` requires replaying its
function against a newer committed value; ``ensure`` requires read locks that
survive the transaction; both deserve a separate correctness proof. The test
gate is a deterministic barrier-driven two-ref conflict test, randomized
operation histories checked against a serialized model, validator and watch
ordering tests, nested transaction tests, and a high-contention stress suite.

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
nREPL server. The local implementation preserves reader source text, dynamic
REPL history, output/error events, tap forwarding, and structured exceptions.
Before adding a remote server, the two protocols should share an extracted
evaluator/session service rather than continuing to duplicate reader,
compiler, source-location, and dynamic-binding behavior.

The internal service receives code plus session state and emits ordered events.
Its initial event model is the Clojure pREPL contract:

* exactly one ``{:tag :ret :val ... :ns ... :ms ... :form ...}`` event per
  successfully read form;
* zero or more ``:out`` and ``:err`` events during evaluation;
* ``:exception true`` plus structured Basilisp exception data on evaluation or
  reader failure; and
* explicitly unsupported values represented through a safe printed form rather
  than arbitrary Python object serialization.

``prepl`` operates over supplied readers and callbacks for deterministic tests.
``io-prepl`` writes one EDN map per line, using ``pr-str`` for return values.
``server-make`` now adds a loopback-default socket server, one isolated
namespace per connection, newline-delimited EDN framing, bounded incremental
input buffering, and clean shutdown. It is deliberately distinct from nREPL's
bencode transport. The next remote phases are request identifiers,
authentication hooks, cancellation, CLI exposure, and concurrent-connection
stress transcripts.

The evaluator boundary should be a small Python service rather than a network
handler: ``evaluate(form_text, session, emit) -> session``. ``session`` owns
the current namespace, dynamic bindings, history, and a cancellation token;
``emit`` receives only Basilisp values. ``prepl`` supplies a reader and callback
to that service. ``io-prepl`` serializes each event as one EDN value per line.
Only then should ``remote-prepl`` add framed sockets, authentication hooks,
message-size limits, and loopback-by-default binding.

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
is a separate project: first prove that a sample ``.lpy`` package builds an
sdist and wheel containing source and valid namespace cache artifacts through
the existing Maturin backend. Only then decide whether a wrapper backend is
necessary. An interactive ``add-lib`` must manage an explicitly selected Python
environment and require a restart when imports cannot be made safe; it must not
silently invoke a second package manager in the running process.

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
handles generic code lists and symbols, reader macros, definition forms,
binding forms, and ``cond``-style pairs, and falls back to ordinary list
printing for incomplete or unrecognized forms. Future dispatch additions such
as ``case``, ``try``/``catch``/``finally``, ``ns``, and ``require`` should use
the same fallback and golden-test approach.

``cl-format`` remains deliberately out of scope. It is a separate, large
format-language implementation with its own argument-consumption and locale
semantics. A Python ``format`` wrapper would not be compatible and must live
under a Python-native name if one is useful.

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

The ``loop`` closure bug should be addressed independently by inspecting the
generated binding cells. A function created before ``recur`` must close over
the old iteration values, while a later iteration receives fresh rebound local
names. Tests should exercise one and multiple loop locals, nested closures,
lazy realization after loop exit, and no recursion growth.

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
``multi-spec``. Explain data is a stable Basilisp data structure before
human-readable explanation or instrumentation is added. Generators and function
instrumentation are later because they require a shrinking/property-testing
model and callable boundary policy. Hypothesis is a good optional test adapter,
not the implementation of the spec contract.

Python interoperability should remain direct rather than imitate Java
interoperability. The next native layer should add narrow, explicit adapters for
dataclasses, ``attrs``, Pydantic models, mappings, sequences, and asynchronous
iterables. Each adapter must state conversion direction, metadata policy,
validation/error representation, and whether it copies or views data. Python
type hints can enrich generated call boundaries only when they are declarative;
they must never cause runtime imports or change dynamic dispatch. JVM-only
facilities such as ``gen-class``, classpath mutation, Java beans, JDBC streams,
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
``conform`` or ``explain-data`` means. Function instrumentation follows with
explicit Var wrapping and ``unstrument`` restoration, never monkey-patching
arbitrary Python callables.

The adapter policy is deliberately conservative because the three model systems
do not mean the same thing by validation. Dataclasses primarily describe field
layout, attrs can run converters before validators, and Pydantic may parse and
coerce values. Therefore an adapter's default read path must produce ordinary
Basilisp data without validation side effects. Its construction path must make
coercion explicit, preserve field aliases and defaults in metadata, and convert
framework validation failures into ordinary, documented problem data rather
than pretending they are native spec failures. The first deliverable should be
a dataclass ``datafy`` adapter because it needs no optional dependency; attrs
and Pydantic follow as isolated contrib packages with contract fixtures.

Python interop should similarly prefer narrow vocabulary over Java-shaped
aliases. Add adapters for mappings, sequences, asynchronous iterables, and
model objects only where conversion direction, copying behavior, and error data
are documented. For typed binary data, use a separate Python-native
``memoryview``/``array`` adapter rather than claiming Java primitive-array
compatibility. For database cursors and URLs, expose cursor and
``urllib.parse`` adapters rather than ``resultset-seq`` and ``uri?``.

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

Libraries that are primarily useful abstractions but depend on Java services
should receive a native Basilisp implementation only when their public contract
is valuable independently of the JVM. Otherwise, document the missing runtime
service and point users to the appropriate Python library. This distinction
keeps the fork from accumulating compatibility names whose behavior surprises
both Clojure and Python users.
