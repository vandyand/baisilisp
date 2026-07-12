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

An experimental ``basilisp.stm`` namespace must precede ``basilisp.core/ref``.
Its first milestone needs versioned immutable references, transaction-local
read/write sets, stable lock ordering, validation at commit, conflict retries,
and state-machine contention tests. ``commute``, history controls, deferred
agent sends, and ``io!`` follow only after that base contract is proven.

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
