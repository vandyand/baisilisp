.. _parity_decisions:

Parity Decision Records
=======================

This document refines the unresolved areas in :ref:`parity_architecture` into
implementation decisions. It is deliberately narrower than the roadmap: a
decision records the public contract, rejected alternatives, and the evidence
required before a feature can be advertised as compatible.

Dependency Admission
--------------------

An external package with a familiar name is not, by itself, a solution to a
Clojure compatibility gap. A required runtime dependency must:

* support Basilisp's supported Python range (3.10+) and not rule out PyPy
  without an explicit platform decision;
* have a license suitable for inclusion in an EPL-1.0 project, subject to
  maintainer and legal review;
* provide the required semantic contract rather than merely a similar API;
* demonstrate sustained maintenance, reproducible tests, and a stable public
  interface; and
* remain optional when it represents a host-framework integration rather than
  a Basilisp runtime primitive.

Packages which fail any of these tests can still be useful as test references
or optional application-level integrations. Their code and implementation
details must not be copied without a separate license review.

Transactional Memory
--------------------

**Decision:** retain the in-tree optimistic STM as the runtime foundation;
do not adopt a third-party STM package.

The current ``basilisp.lang.stm`` implementation already owns the essential
first contract: versioned ``Ref`` values, transaction-local read/write sets,
stable lock ordering at commit, validators, post-commit watches, nested
transactions, retry on conflict, and rejection of awaitable transaction
bodies. That is closer to the Basilisp object and reference model than an
adapter could be.

The current candidate most likely to appear in a package search, `Atomix STM
<https://pypi.org/project/atomix-stm/>`_, is not an acceptable dependency. It
is GPLv3/commercially licensed, has a small and very recent public history, and
its own release notes record several recent concurrency-correctness fixes. It
may be used to derive adversarial test scenarios, but not as a runtime base.
`ZODB's transaction package
<https://zodb.org/en/latest/reference/transaction.html>`_ is maintained and
useful for two-phase coordination of storage resources, but it does not supply
the in-memory versioned snapshot or multi-``Ref`` commit required by ``dosync``.
It belongs, if anywhere, in a future storage adapter rather than in ``Ref``.

The next STM phases are intentionally ordered:

1. **Completed locally:** ``io!`` rejects explicitly marked impure operations,
   and transaction-local after-commit actions defer agent sends until the final
   commit. Neither mechanism can detect arbitrary Python side effects.
2. **Completed locally:** experimental ``run-transaction`` accepts a bounded
   retry count and raises structured conflict data on exhaustion. Compatibility
   ``dosync`` retains retry-until-success behavior.
3. **Completed locally:** ``commute`` records operation functions and arguments
   separately from normal writes, then replays them under the commit locks. A
   commute must not silently become an ``alter``: concurrent changes to a
   commuted Ref are permitted, so callers remain responsible for commutativity
   and retry-safe functions.
4. **Completed locally:** ``ensure`` returns the in-transaction value and marks
   a Ref for version validation when it would otherwise be a pure commute.
5. **Measured locally:** ``scripts/stm_contention_probe.py`` ran three forced-
   yield rounds of 16 workers performing 250 transactions each. All 12,000
   commits completed with 1.002--1.004 mean attempts and a worst-case of two
   attempts. Together with the deterministic conflict and Hypothesis history
   tests, this shows normal retry cost but no starvation, so do not add
   Clojure's adaptive history queue yet. History is an optimization for snapshot
   retention, not a prerequisite for atomic multi-Ref updates.
6. **Completed locally:** portable ``Ref`` operations are exposed from
   ``basilisp.core``: ``ref``, ``dosync``, ``alter``, ``ref-set``, ``commute``,
   and ``ensure``. The shared Clojure/Basilisp Ref fixture verifies sequential
   transaction, nesting, watch, validator, metadata, commute, and ensure
   behavior. Unqualified ``await`` remains an async special form, while the
   qualified ``clojure.core/await`` spelling provides Clojure's agent wait
   contract alongside ``await-agent``.

This ordering follows the observable Clojure contract: transactions are
atomic, consistent, isolated, and retry on conflict; ``commute`` deliberately
permits changes to its target Ref; and ``ensure`` protects an otherwise
unchanged Ref used in a cross-Ref constraint. See `Clojure's Ref documentation
<https://clojure.org/refs>`_.

Before each phase is promoted, run deterministic two-thread conflict fixtures,
randomized operation histories compared with a serialized reference model,
validator/watch ordering tests, retry side-effect tests, and a high-contention
stress suite. `Hypothesis rule-based state machines
<https://hypothesis.readthedocs.io/en/latest/stateful.html>`_ are appropriate
for the operation-history portion because they shrink a failing sequence.

Channels And Async Interoperability
-----------------------------------

**Decision:** ``basilisp.concurrent.Channel`` remains the asyncio-native
primitive. Do not replace it with ``asyncio.Queue``, AnyIO, or a third-party
channel package.

The local channel already represents operations Clojure programmers expect to
reason about: a true zero-capacity rendezvous, fixed/sliding/dropping buffers,
close, non-blocking offer/poll, cancellation cleanup, selection, and timeout.
It also has the right ownership boundary: one event loop per channel. An
``asyncio.Queue`` cannot provide this directly because a max size of zero is an
unbounded queue, not a rendezvous.

AnyIO is a strong optional interoperability target, not a replacement runtime.
Its `memory object streams <https://anyio.readthedocs.io/en/stable/streams.html>`_
do provide a rendezvous at buffer size zero, but they use distinct send and
receive endpoints, clone semantics, backend-specific cancellation behavior,
and close exceptions. A transparent wrapper would therefore lie about one API
or the other. Do not add an adapter until a real AnyIO/Trio consumer exists.
When one does, expose explicit ownership-transfer helpers in a separate
``basilisp.contrib.anyio`` namespace rather than make an AnyIO endpoint pretend
to be a bidirectional Basilisp ``Channel``.

``pipe!`` and ordered ``pipeline!`` now provide the next channel milestone,
using normal synchronous transducers without pretending to implement ``go``.
The pipeline owns an explicit task, admits bounded work, preserves input order,
handles fan-out, closes output explicitly, and performs cancellation-safe task
cleanup. The
``go`` macro remains a compiler project: it must turn eligible bodies into
resumable state machines and reject unsupported control flow deterministically.
Until it has that proof, ``defasync`` plus ``await`` is the honest spelling.

Function Specs, Generators, And Python Models
----------------------------------------------

**Decision:** complete portable ``spec.alpha`` first; make function checking
and Python model integrations opt-in layers over that core.

The first function-spec milestone now provides an ``fspec`` descriptor and a
separate function-spec registry keyed by an interned Basilisp ``Var``:

* ``fdef`` records ``:args``, ``:ret``, and optional ``:fn`` specifications.
* ``fspec`` describes a callable result, including higher-order return values.
  Merely checking that a Python value is callable cannot prove its argument or
  result behavior, so ``valid?`` must not imply that it has executed a function
  contract. Argument, return, and relation validation begins only with an
  explicitly instrumented call or generated check.
* ``basilisp.spec.test.alpha/instrument`` validates arguments at calls through
  an instrumented Basilisp Var. It must update the Var and its current module
  binding, preserve the original callable for ``unstrument``, and decline to
  monkey-patch arbitrary foreign Python callables. Existing references imported
  before instrumentation are explicitly outside the guarantee.
* Generated checking invokes a Var with generated conforming arguments, then
  checks ``:ret`` and ``:fn``. This mirrors the separation in `Clojure spec
  <https://clojure.org/guides/spec>`_: instrumentation checks callers' args;
  generative checking evaluates the implementation.

Hypothesis is an optional ``spec-test`` dependency. Native strategies now cover
portable scalar classes, regex argument grammars, ``nilable``, ``or``, tuples,
collections, ``map-of``, and ``keys`` descriptors. Require ``with-gen`` for an
arbitrary predicate, ``and``/``&`` relation, multi-spec, or any other domain
without a constructive generator rather than filtering random values until one
happens to conform. Hypothesis supplies shrinking and reproducible seeds; it
must not define ``conform`` or ``explain-data`` semantics.

Python models are adapters, not implicit specs. The dataclass adapter establishes
the pattern: an explicit shallow data projection and a separately named,
non-coercing construction operation. The next adapters should be:

* **Completed locally:** ``basilisp.contrib.attrs`` projects declared attrs
  fields without invoking converters or validators. Its ``from-data`` adapter
  passes values to the generated attrs initializer, where attrs converters run
  before validators as documented by `attrs
  <https://www.attrs.org/en/stable/init.html>`_.
* ``basilisp.contrib.pydantic``: an optional dependency with a projection based
  on ``model_dump`` and a separately named validation construction operation.
  The API must expose strictness, aliases, and extra-field policy. Pydantic may
  coerce input, drop extra fields by default, and return a normalized model, so
  it cannot be named as though it were a pure ``spec`` conformance operation.
  See the `Pydantic model contract
  <https://pydantic.dev/docs/validation/latest/concepts/models/>`_.

Neither adapter may register global specs, import application model modules
implicitly, or change normal protocol dispatch.

pREPL And Diagnostics
---------------------

**Decision:** make the structured evaluator the unit of reuse and keep the
socket server local-only until there is a complete remote-execution security
model.

**Completed locally:** ``basilisp.contrib.repl_session`` is the shared Python
form evaluator used by pREPL and nREPL. It owns namespace and dynamic history
bindings, compiler execution, namespace transitions, and output/error stream
capture. pREPL retains reader/source text and structured events; nREPL retains
its request batching, bencode response formatting, and final-result history
semantics. Socket and EDN-line transports are therefore adapters rather than
independent evaluators.

Remote pREPL is remote code execution. ``server-make`` is therefore constrained
to loopback addresses; a configurable non-loopback host is not an adequate
security design. ``remote-prepl`` provides the complementary client transport,
with bounded event lines and adversarial/concurrent transcripts, but it does
not publish a listener or claim authentication. It may connect through a
user-provided authenticated tunnel. Do not treat a bare token on an
unencrypted socket as a remote security model. A non-loopback listener still
requires request identifiers, cooperative cancellation, authentication, and
transport encryption or a documented tunnel boundary.

The compiler already exposes structured exception data with phase, file, form,
and source spans. Extend that existing representation instead of inventing a
second diagnostics hierarchy. The remaining work is to make pREPL, nREPL, CLI,
and human tracebacks render the same cause chain and source data consistently.
Synchronous evaluation interruption remains cooperative in-process; a hard
timeout must execute in a disposable worker process rather than attempt to
kill a Python thread.

Project Configuration And Builds
--------------------------------

**Decision:** the existing ``[tool.basilisp]`` resolver is the project model;
Maturin remains the build backend until a fixture proves it cannot package
normal Basilisp source correctly.

The resolver already centralizes source paths, test paths, and compiler options
for the CLI. **Completed locally:** ``scripts/package_probe.py`` builds the
current package into an sdist and wheel through Maturin, asserts representative
``.lpy`` sources are included, installs each artifact into a clean environment,
imports ``core``, ``datafy``, and ``spec.alpha``, and verifies namespace cache
creation. It is intentionally a black-box artifact probe rather than a unit
test of Maturin internals.

Only a failing probe justifies ``basilisp.build``. A future wrapper backend
must delegate to the established native-extension build path, implement the
standard PEP 517 hooks, and remain a distribution mechanism only. `PEP 517
<https://peps.python.org/pep-0517/>`_ defines a build-backend interface, not a
dependency resolver. Dependency resolution, environment selection, lock files,
and installation remain the responsibility of Python frontends such as uv,
pip, Poetry, or Hatch. ``add-lib`` must therefore stay out of scope until it
can make an explicit environment mutation and require a restart.

XML And Library Portability
---------------------------

**Decision:** expose a small ``basilisp.xml`` immutable-tree adapter through the
normal ``clojure.xml`` import-path alias; do not expose a mutable ElementTree
wrapper.

``xml.etree.ElementTree`` expands names to ``{uri}local`` and uses a global
prefix registry during serialization. `Its namespace API
<https://docs.python.org/3/library/xml.etree.elementtree.html>`_ therefore
cannot reproduce a Clojure-style map contract while also preserving lexical
prefix choices, namespace scope, mixed content, and useful error data. ``lxml``
would add a native dependency and still requires a representation decision; it
does not solve that API mismatch.

``basilisp.xml`` now uses the portable, data-oriented subset directly:
``{:tag keyword :attrs {keyword string} :content [string-or-element ...]}``.
Child order and non-whitespace mixed content are retained, while whitespace-only
text nodes are omitted as in ``clojure.xml``. Parsing rejects DTDs and entity
declarations before ElementTree sees them, limits all text inputs to 4 MiB by
default (configurable with ``:max-chars``), and reports malformed XML through
the host parser exception. It accepts document strings, paths/URLs, and readable
text streams.

The adapter rejects qualified and non-ASCII names on both parse and emit rather
than silently losing ElementTree's ``{uri}local`` normalization or fabricating
namespace declarations. It also rejects namespace-qualified Basilisp keywords.
Emission escapes text and attributes, sorts attributes by name, and does not
promise byte, prefix, namespace, comment, processing-instruction, or streaming
round trips. A future namespace-aware semantic tree must be a separate, explicit
contract rather than a silent extension of this subset.

Likewise, library portability stays source-led. A Clojure library is portable
only when its source and transitive dependencies are portable, its reader
conditionals contain a viable ``:lpy`` path, and its tests pass with documented
substitutions. The manifest is the proof artifact. Basilisp will not load JARs
or resolve Maven coordinates; native ports ship as Python distributions.

The first upstream screening identified ``clojure/tools.cli`` at pinned
revision ``865e988`` as needing an explicit host-exception policy: its source
catches JVM ``Throwable`` through a ``:clj``/``:cljs`` reader conditional with
no viable ``:lpy`` branch. The admitted ``basilisp.tools.cli`` port maps those
recoverable parsing and validation callbacks to ``python/Exception``. It
deliberately does not catch ``BaseException``: ``KeyboardInterrupt``,
``SystemExit``, and other Python control signals remain observable. The port
and this policy are exercised against a data-only contract derived from the
upstream tests; Basilisp does not select the JVM reader branch.

Detailed Resolution Boundaries
------------------------------

The remaining gaps are not all implementation backlogs. Some need an adapter,
some need a compiler proof, and some are intentionally unportable. The
following decisions make that distinction concrete before a public API is
added.

STM Dependencies And History
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Decision:** do not replace ``basilisp.lang.stm`` with a package. Use external
transaction packages only behind an explicitly separate storage integration.

The candidate space has two materially different kinds of project:

* `Atomix STM <https://pypi.org/project/atomix-stm/>`_ advertises STM-like
  behavior, but its GPLv3 license, Python 3.13+ baseline, and independent
  ``Ref`` model rule it out as a Basilisp runtime dependency. It can inform
  adversarial scenarios only.
* `ZODB transaction <https://transaction.readthedocs.io/en/stable/>`_ is a
  maintained two-phase coordinator for resource managers. It does not own a
  versioned snapshot of in-memory Basilisp ``Ref`` values, and its transaction
  boundary is not a retryable ``dosync`` body. It is a possible future
  ``basilisp.contrib.zodb`` integration, not an STM engine.

The in-tree engine remains responsible for read-set validation, atomic
multi-Ref publication, retry boundaries, validator and watch order, and
deferred after-commit actions. A storage adapter may register an after-commit
action or participate in a separately documented two-phase commit; it may not
silently make a ``dosync`` durable or distributed.

Ref history should remain absent until a workload demonstrates starvation or
unacceptable retry behavior. The decision input is a repeatable workload with
contention shape, completion distribution, retry percentiles, and a serialized
reference-model check. If history is then needed, add bounded per-Ref committed
versions solely to retain a read snapshot; do not expose JVM-specific tuning
knobs by name. Bounded ``max-attempts`` and structured conflict information are
the application-level escape hatch. No backoff policy should be introduced by
default because it changes both scheduling and observable retry behavior.

Async Pipelines And ``go``
^^^^^^^^^^^^^^^^^^^^^^^^^^

**Decision:** extend the local channel with Python-native pipeline helpers;
do not claim ``core.async`` or add a ``go`` alias.

The first API should live in ``basilisp.concurrent`` and be deliberately
small: a ``pipe!`` forwarding task, an ordered ``pipeline!`` for a synchronous
transducer, and a separately named asynchronous pipeline when a real consumer
requires one. ``pipeline!`` accepts a concurrency limit, input and output
channels, a transducer, an explicit close-output option, and an explicit error
handler. It returns an application-owned task or supervisor handle rather than
hiding background work. Each input is transformed independently, may produce
zero or more results, and output order is retained by sequence number. This
matches the important contract of `core.async pipeline
<https://clojure.github.io/core.async/reference.html>`_ without pretending that
the execution substrate is the JVM.

The implementation should use the existing reducer/transducer protocol, not
reimplement the transformations for channels. It needs a bounded work queue,
one ordered result queue, cancellation propagation in both directions, and a
single point that closes the output once all admitted work has either completed
or failed. A closed output must stop upstream consumption; a closed input must
drain admitted work before output close. Error handling must state whether the
failing element is dropped, transformed to a replacement result, or terminates
the pipeline.

The required test suite is deterministic first: ordered fan-out, reduced
completion, early output close, input close while work is pending, and handler
failure. It then needs randomized producer/consumer cancellation schedules
that prove no duplicate, lost, or post-close values and that every task is
joined. Only after that is stable should asynchronous mapping be considered.
``defasync`` and ``await`` remain the supported spelling for async work.
Implementing ``go`` correctly would require a compiler-produced resumable state
machine and defined rejection for unsupported Python control flow; a macro that
merely wraps ``defasync`` would misrepresent that contract.

AnyIO And Task Ownership
^^^^^^^^^^^^^^^^^^^^^^^^

**Decision:** no general AnyIO wrapper. A future optional adapter is limited to
the AnyIO asyncio backend and performs explicit value transfer.

AnyIO memory streams genuinely support zero-capacity rendezvous, but they have
separate send/receive endpoints, clone lifetimes, and close exceptions that do
not match ``Channel``. They also run on Trio, whereas a Basilisp ``Channel`` is
intentionally bound to an asyncio event loop. `AnyIO's stream contract
<https://anyio.readthedocs.io/en/stable/streams.html>`_ makes a transparent
bidirectional wrapper incorrect on both sides.

When a consumer justifies it, ``basilisp.contrib.anyio`` should require the
AnyIO asyncio backend and expose two one-way coroutines, conceptually
``copy-channel-to-send!`` and ``copy-receive-to-channel!``. Each receives a
caller-owned source and destination, defines whether it closes the destination
on normal source completion, and propagates cancellation without closing
resources it does not own. It must reject a non-asyncio backend clearly. A
Trio-capable Basilisp channel would be a separate backend abstraction project,
not an adapter patch.

Pydantic And Python Data Models
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Decision:** keep Pydantic optional and target V2 only when an application
needs it. It is a validation and serialization boundary, never a global spec
provider.

The adapter should mirror the dataclass and attrs shape while making Pydantic's
coercion visible:

* ``datafy`` calls ``model_dump`` with explicit options, defaults to field
  names rather than aliases, and records the original object/class as metadata.
  It must document whether nested models are recursively projected.
* ``from-data`` accepts only a model class and a map with unqualified keyword
  or string keys, converts keys to strings, and calls ``model_validate``.
  It exposes ``:strict?``, ``:by-alias?``, and ``:by-name?`` rather than
  silently inheriting a surprising conversion policy.
* Validation errors remain Pydantic errors with a structured Basilisp wrapper
  containing the input-key policy and the original error data. It must neither
  drop unknown input before validation nor bypass validation with
  ``model_construct``.

Pydantic documents both coercive validation and a strict mode, along with
``model_dump`` and ``model_validate`` as its primary boundary APIs; see its
`model documentation <https://pydantic.dev/docs/validation/latest/concepts/models/>`_. Required
fixtures cover aliases, defaults, extras under each model policy, nested
models, strict and coercive validation, computed/private fields, and a V1
model rejection. This is explicitly distinct from ``spec.alpha`` conformance.

Diagnostics And Method Signatures
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Decision:** normalize existing exception data for every renderer, and improve
method-signature feedback only when Python introspection is authoritative.

**Completed locally:** ``basilisp.lang.diagnostics/exception_data`` is the
internal normalizer, not a new exception class. It consumes
``CompilerException.data``, ``ExceptionInfo.data``, and foreign exceptions and
produces a persistent map containing phase, message, exception class, source
span, form when available, and an ordered cause chain. pREPL exception events
now use that representation while preserving their existing envelope. nREPL
eval errors retain standard ``err`` and ``ex`` fields and additionally expose
the EDN rendering under ``basilisp/diagnostic``.

CLI text and human tracebacks now preserve their existing traceback formatting
and append the same readable EDN map under a ``Basilisp diagnostic:`` label.
Transport-specific fields such as request id, stream text, and bencode status
remain adapters outside the core diagnostic data. Fixtures now assert compiler
and runtime diagnostic type, phase, source, and cause data across pREPL, nREPL,
CLI, and direct human traceback rendering.

The analyzer already checks known abstract members and can inspect ordinary
Python signatures when ``:warn-on-arity-mismatch`` is active. These warnings
now include a source span and structured diagnostic data, rather than
converting every mismatch into an error. It may issue a precise diagnostic only
when the base class is statically resolved and ``inspect.signature`` succeeds
with an unambiguous positional contract. Builtins, extension methods,
decorators without recoverable signatures, defaults, keyword-only parameters,
and dynamically resolved bases should retain the existing conservative warning
or runtime behavior. `inspect.signature
<https://docs.python.org/3/library/inspect.html#inspect.signature>`_ explicitly
does not guarantee introspection for every callable. Tests must distinguish
known exact matches, known wrong fixed/variadic arity, uninspectable methods,
and dynamic bases; no guesswork should turn valid Python interop into a compile
error.

Python-Native Host Interop
^^^^^^^^^^^^^^^^^^^^^^^^^^

**Decision:** expose Python facilities under Python-native namespaces and add
adapters only where a stable data contract exists. Do not create Java-named
facades for different host concepts.

``bean``, Java primitive arrays, JDBC result sets, Java streams, and Java URI
objects should remain intentional omissions. Their appropriate Python-native
counterparts are ``datafy`` adapters for declared models, ``array`` and
``memoryview`` for binary data, DB-API cursors for rows, iterators/async
iterators for streams, and the existing ``basilisp.url``/``urllib.parse``
support for URLs. Future integrations should be separate optional namespaces,
for example a DB-API row projection that rejects duplicate column names unless
the caller supplies a policy, or a binary buffer adapter that documents byte
order and mutability. Neither belongs in ``basilisp.core`` or should be named
``resultset-seq`` or ``uri?``.

XML now has a bounded immutable-tree adapter for the data-oriented subset.
Namespace/prefix fidelity, comments, processing instructions, and streaming are
deliberately still separate work. Python's XML security guidance identifies
additional denial-of-service concerns and points to ``defusedxml`` for broader
untrusted-document requirements; see `the standard library XML security notes
<https://docs.python.org/3/library/xml.html#xml-vulnerabilities>`_. Do not widen
the adapter's boundary without namespace, malformed-input, mixed-content,
serialization, and size-limit fixtures.

Execution Order
---------------

The completed local work covers diagnostics, conservative inherited-method
signature warnings, the first channel pipeline milestone, and portable Ref
operations. The differential corpus now covers portable core collection,
sequence, transducer, metadata, hierarchy, lazy-realization, macro-expansion,
exception-data, ``seque``, ``clojure.test`` reporting, and deterministic
Agent/Ref behavior; ``sync`` is included as compatible transaction syntax.
There is now also a source-level multi-file library acceptance proof with a
checked-in portability manifest and Clojure/Basilisp test-summary comparison.
The next work is:

1. Expand the source-level acceptance corpus from its representative portable
   library to small upstream candidates. Keep reader conditionals limited to
   documented standard-namespace substitutions; add public compatibility names
   only after a shared fixture and manifest pass. Continue to omit Ref history
   controls unless a workload demonstrates starvation or snapshot-retention
   pressure.
2. Do not add a ``go`` macro until resumable-state-machine semantics have a separate
   proof and rejection model.
3. Defer Pydantic and AnyIO adapters until there is a consumer; both require a
   separately tested conversion and ownership contract.

This sequence closes high-value semantic gaps while preserving the distinction
between Clojure compatibility and Python-native capabilities.
