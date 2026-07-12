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
   yield rounds of eight workers performing 100 transactions each. All 2,400
   commits completed with roughly 3.3--3.6 mean attempts and worst-case retries
   in the tens. This shows normal retry cost but no starvation, so do not add
   Clojure's adaptive history queue yet. History is an optimization for snapshot
   retention, not a prerequisite for atomic multi-Ref updates.

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

The next channel milestone is transducer/pipeline support, not a ``go`` macro.
The macro is a compiler project: it must turn eligible bodies into resumable
state machines and reject unsupported control flow deterministically. Until it
has that proof, ``defasync`` plus ``await`` is the honest spelling. Tests for
the pipeline milestone must cover cancellation, early close, no loss or
duplication, backpressure, and selection fairness under randomized schedules.

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

Hypothesis should be an optional ``spec-test`` dependency. Use native
strategies for descriptors with known domains and require ``with-gen`` for an
arbitrary predicate rather than filtering random values until one happens to
conform. Hypothesis supplies shrinking and reproducible seeds; it must not
define ``conform`` or ``explain-data`` semantics.

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

Remote pREPL is remote code execution. A configurable non-loopback host is not
an adequate security design. The next hardening patch should either constrain
``server-make`` to loopback addresses or require an explicit unsafe opt-in that
is clearly documented for use behind SSH or another authenticated tunnel.
Do not treat a bare token on an unencrypted socket as a remote security model.
Remote support requires message-size limits, per-request identifiers,
cooperative cancellation, authentication, transport encryption or a documented
tunnel boundary, and transcript/concurrency stress tests.

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

**Decision:** do not add a thin ``clojure.xml`` alias. If XML becomes a real
need, create a separately named Basilisp-native XML data adapter with an
explicit namespace policy.

``xml.etree.ElementTree`` expands names to ``{uri}local`` and uses a global
prefix registry during serialization. `Its namespace API
<https://docs.python.org/3/library/xml.etree.elementtree.html>`_ therefore
cannot reproduce a Clojure-style map contract while also preserving lexical
prefix choices, namespace scope, mixed content, and useful error data. ``lxml``
would add a native dependency and still requires a representation decision; it
does not solve that API mismatch.

If implemented, ``basilisp.xml`` should use an immutable semantic tree with
separate URI, local-name, optional preferred-prefix, attributes, namespace
declarations, text/tail content, and child order. It may offer an explicitly
lossy conversion to a simple map for data-oriented consumers. It must not
promise byte-for-byte or prefix-for-prefix XML round trips. Safe parsing,
malformed-input exception data, and streaming limits are part of the first
contract, not later polish.

Likewise, library portability stays source-led. A Clojure library is portable
only when its source and transitive dependencies are portable, its reader
conditionals contain a viable ``:lpy`` path, and its tests pass with documented
substitutions. The manifest is the proof artifact. Basilisp will not load JARs
or resolve Maven coordinates; native ports ship as Python distributions.

Execution Order
---------------

The most appropriate next work is:

1. Unify pREPL, nREPL, CLI, and human-facing diagnostic rendering around the
   existing structured exception data before adding cancellation or remote
   transport features.
2. Repeat ``scripts/stm_contention_probe.py`` at realistic production-like
   workloads before considering history controls. The current forced-yield
   sample shows retry cost but no starvation; do not claim JVM STM internals
   without a measurable need and a separate proof.
3. Broaden explicit ``fspec`` generation only where a portable descriptor has a
   well-defined Hypothesis strategy; do not synthesize arbitrary predicates.
4. Run the sample package build/install probe before considering a new backend.
5. Defer Pydantic and AnyIO adapters until there is a consumer; both require a
   separately tested conversion and ownership contract.

This sequence closes high-value semantic gaps while preserving the distinction
between Clojure compatibility and Python-native capabilities.
