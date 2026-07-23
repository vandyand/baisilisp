.. _parity_roadmap:

Parity Roadmap
==============

This roadmap describes one practical direction for a downstream Basilisp fork:
preserve Clojure compatibility where it improves portability and correctness,
while leaning into Python where the host runtime gives Basilisp a better native
answer than copying JVM behavior.

The goal is not perfect Clojure emulation. The goal is a Clojure-compatible
Python Lisp that is easier to build, package, test, debug, and use with the
Python ecosystem.

Compatibility Baseline
----------------------

Basilisp already supports a substantial amount of idiomatic Clojure:

* immutable collections
* namespaces
* macros
* protocols, records, and types
* multimethods
* dynamic Vars and ``binding``
* atoms and other reference-like primitives
* the reader and EDN data
* ``basilisp.test``
* Python interop through imports, member access, keyword arguments, and
  Python literals
* ports of core libraries including ``data``, ``edn``, ``io``, ``pprint``,
  ``math``, ``set``, ``shell``, ``stacktrace``, ``string``, ``test``, ``walk``,
  and ``zip``

The largest compatibility gaps are not only missing individual functions.
They are clustered around project tooling, test compatibility, persistent
collection behavior, missing standard namespaces, and Python runtime
integration.

Roadmap Tracks
--------------

1. Project Tooling
^^^^^^^^^^^^^^^^^^

This is the highest-leverage area for a fork because it affects every new
project and every library author. Basilisp should feel like a normal Python
package while still supporting Lisp source layout and REPL-driven development.

Initial targets:

* project configuration file (`#755 <https://github.com/basilisp-lang/basilisp/issues/755>`_)
* native source path configuration (`#900 <https://github.com/basilisp-lang/basilisp/issues/900>`_)
* PEP 517 build backend (`#1221 <https://github.com/basilisp-lang/basilisp/issues/1221>`_)
* Clojure 1.12 tools support (`#1107 <https://github.com/basilisp-lang/basilisp/issues/1107>`_)
* interactive dependency loading (`#1106 <https://github.com/basilisp-lang/basilisp/issues/1106>`_)
* CLI tooling interface (`#526 <https://github.com/basilisp-lang/basilisp/issues/526>`_)

Near-term deliverable:

* **Completed locally:** a minimal ``pyproject.toml``-first Basilisp project
  contract with source paths, test paths, and compiler options for CLI tools
* next, prove a sample Basilisp package can build and install through the
  existing Maturin backend before deciding whether a dedicated PEP 517 wrapper
  is needed

2. Test Compatibility
^^^^^^^^^^^^^^^^^^^^^

Test behavior is a high-confidence way to close the parity gap because it is
easy to reproduce, easy to verify, and immediately useful for porting Clojure
libraries.

Initial targets:

* custom ``assert-expr`` support (`#1334 <https://github.com/basilisp-lang/basilisp/issues/1334>`_)
* Clojure-style fixtures in the PyTest runner (`#1306 <https://github.com/basilisp-lang/basilisp/issues/1306>`_)
* simple ``basilisp.test`` runner (`#980 <https://github.com/basilisp-lang/basilisp/issues/980>`_)
* source-accurate assertion failures (`#635 <https://github.com/basilisp-lang/basilisp/issues/635>`_)

Near-term deliverable:

* make ``basilisp.test`` close enough to ``clojure.test`` that compatibility
  failures can be classified as real language/runtime gaps instead of test
  harness gaps

3. Core And Collection Parity
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Core collection behavior is foundational. Many Clojure libraries assume sorted
collections, seq behavior, hashing behavior, regex helpers, and reader helper
functions exist.

Initial targets:

* sorted sets, sorted maps, and array maps (`#416 <https://github.com/basilisp-lang/basilisp/issues/416>`_)
* efficient ``drop`` and partition support (`#1110 <https://github.com/basilisp-lang/basilisp/issues/1110>`_)
* missing core functions and macros (`#375 <https://github.com/basilisp-lang/basilisp/issues/375>`_)
* protocol extension by metadata (`#630 <https://github.com/basilisp-lang/basilisp/issues/630>`_)
* agents (`#413 <https://github.com/basilisp-lang/basilisp/issues/413>`_)

Near-term deliverable:

* maintain a generated matrix comparing public ``basilisp.core`` vars against
  the corresponding Clojure public vars, with each missing symbol classified as
  implement, omit, host-specific, or needs design
* use ``scripts/core_parity_matrix.py`` as the initial raw source for that
  matrix. Its ``--basilisp-command`` option accepts a frontend-specific command
  prefix, for example ``uv run basilisp run -c`` when measuring this checkout.
* use ``scripts/differential_conformance.py`` for portable behavioral fixtures.
  By default it evaluates every ``tests/conformance/*_cases.cljc`` source file
  in Clojure and Basilisp and compares parsed EDN, so map print order and other
  non-semantic formatting cannot hide or create a compatibility difference.
  The corpus covers core collection/sequence/transducer/metadata/hierarchy and
  lazy-realization behavior, macro expansion, exception data, shared-core edge
  semantics, ``seque``, deterministic Agent/Ref transactions, a seeded
  pseudo-random Ref operation corpus with validator aborts, loop closure
  capture across ``recur`` iterations and lazy realization after loop exit,
  ``instant`` timestamp parsing and ``#inst`` reader behavior, and
  ``clojure.test`` assertion, reporting, custom-assertion, and fixture effects.
  It also includes a deliberately string-rendered ``pprint`` fixture for
  portable pretty-printing contracts where the rendered text is the public
  behavior.
  New public compatibility names should arrive with a portable fixture or a
  documented host-specific reason why a shared fixture is impossible.
* treat the upstream ``clojure-test-suite`` result as a triage input, not a
  direct implementation queue. The current residual suite failures are
  classified in ``docs/core-parity-needs-review.md`` so stale ``:lpy`` branches,
  host-specific behavior, and explicitly undefined Clojure behavior do not
  receive compatibility-shaped runtime patches by accident. A failing upstream
  case should become implementation work only after a portable fixture proves
  the same behavior against JVM Clojure. The residual ignore helper also checks
  that each excluded external file has a structured classification and an
  existing local conformance fixture before emitting pytest ``--ignore``
  arguments for CI.
* use ``scripts/library_acceptance.py`` for a source-level, multi-file library
  proof. It executes the library-owned ``run.cljc`` test entrypoint in Clojure
  and Basilisp, compares the final EDN summary, and rejects a stale checked-in
  manifest. Use ``--all`` to run every checked-in acceptance library in stable
  order. The initial ``tests/acceptance/portable_library`` fixture exercises
  standard ``string``, ``set``, ``walk``, collection, transducer, exception,
  and ``clojure.test`` behavior using only documented ``:clj``/``:lpy``
  namespace substitutions.
  ``tests/acceptance/upstream/cognitect-anomalies`` is the first pinned
  upstream snapshot; run it with ``--library-root`` to prove the unchanged
  source's public spec contract in both runtimes.
  ``basilisp.tools.cli`` is the first substantial upstream port: it retains a
  pinned ``clojure/tools.cli`` source snapshot, a minimal Python-hosted port,
  and a shared parsing/defaults/errors/subcommand acceptance contract. The
  checked-in upstream acceptance corpus also covers ``math-combinatorics``,
  ``medley``, and ``tools-macro``.

4. Standard Namespace Coverage
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Standard namespaces make Basilisp more useful before applications need custom
interop. They also reduce friction when porting small Clojure libraries.

Initial targets:

* pREPL server (`#628 <https://github.com/basilisp-lang/basilisp/issues/628>`_)
* ``pprint`` compatibility, including ``code-dispatch`` and source-derived
  ``cl-format`` coverage (`#1266 <https://github.com/basilisp-lang/basilisp/issues/1266>`_)
* ``core.async`` or a Python-native async alternative (`#149 <https://github.com/basilisp-lang/basilisp/issues/149>`_)

Near-term deliverable:

* prioritize namespaces with small, testable API surfaces before larger
  runtime-level features
* **Completed locally:** close the small portable public-surface gaps in
  ``clojure.string`` and ``clojure.data.priority-map``. ``trim-newline``,
  ``->PersistentPriorityMap``, and ``apply-keyfn`` are now covered by shared
  differential fixtures.
* **Completed locally:** close portable constructor/protocol gaps in
  ``clojure.core.cache``, ``clojure.core.memoize``, and
  ``clojure.core.protocols``, and add the standard ``clojure.core.reducers``
  import path. Shared fixtures now cover cache/memoize generated constructors,
  core protocol reduction helpers, reducers stress cases through the standard
  namespace, and explicit JVM-boundary classification.
* **Completed locally:** close the remaining deprecated
  ``clojure.tools.namespace`` root facade names by mapping classpath discovery
  to Basilisp's Python import path, including directories and ZIP/JAR archives.
* **Completed locally:** close ``clojure.tools.reader`` and
  ``clojure.tools.reader.reader-types`` public surface parity. Shared fixtures
  now cover dynamic Vars, ``map-func``, reader-type constructors/coercers,
  metadata merging, and character-returning ``read-char`` behavior.
* **Completed locally:** close ``clojure.tools.logging.impl`` and the portable
  ``clojure.tools.logging`` dynamic Var/factory surface over Python logging.
  Java backend selectors are documented no-ops; the remaining JVM proxy-class
  public Var is treated as an implementation artifact.
* **Completed locally:** close ``clojure.spec.alpha``,
  ``clojure.spec.test.alpha``, and ``clojure.spec.gen.alpha`` public namespace
  surface gaps. Shared fixtures now cover protocol/helper names, registry and
  explain-data entrypoints, regex implementation helpers, and portable
  ``spec.test.alpha`` summary/symbol helpers. Remaining spec work is semantic
  depth for generation edge cases and explicit Python model adapters, not
  missing public names.
* **Completed locally:** deepen ``clojure.spec.alpha/keys`` semantics for
  ``:req-un``/``:opt-un`` and implement ``keys*`` as an alternating
  keyword/value regex spec. Shared fixtures now lock unqualified-key
  conformance, explain paths, forms/descriptions, generation shape, unforming,
  and ``keys*`` inside ``cat``.
* **Completed locally:** support bounded generation for recursively-defined
  keyword specs with a nonrecursive base branch. Shared fixtures now lock
  self-recursive and mutually-recursive generation as terminating, conforming,
  branch-producing, bounded-depth behavior.
* **Completed locally:** support Clojure-style ``multi-spec`` generation for
  multimethod-backed specs. Shared fixtures now lock keyword retagging,
  function retagging, branch enumeration, generated-value conformance, wrong
  branch rejection, and missing-method rejection.
* **Completed locally:** support portable ``fspec`` function-value generation
  for descriptors with ``:args`` specs. Shared fixtures now lock generated
  invokability, generated return conformance, invalid argument and arity
  rejection, conformed ``:fn`` relation inputs, and the Clojure-compatible
  failure boundary for ``fspec`` generation without ``:args``.
* **Completed locally:** close the portable ``clojure.instant`` public surface
  by adding ``read-instant-date``, ``read-instant-calendar``, and
  ``read-instant-timestamp`` equivalents. Shared fixtures now lock public names,
  UTC Date/Timestamp epoch behavior, offset-preserving calendar fields,
  timestamp nanosecond retention, malformed input rejection, and seeded reader
  corpus behavior.
* **Completed locally:** close the remaining ``clojure.repl`` public names with
  Python-host boundary implementations for ``set-break-handler!``,
  ``thread-stopper``, and ``stack-element-str``. Shared fixtures now lock the
  public surface and stack-element string shape while local tests cover signal
  handler installation/restoration and interrupt behavior.
* **Completed locally:** close the ``clojure.xml`` public surface with
  ``xml/element`` struct maps, ``tag``/``attrs``/``content`` accessors, dynamic
  SAX-state Vars, and Python-host adaptations of ``sax-parser``,
  ``disable-external-entities``, ``startparse-sax``, and
  ``startparse-sax-safe``. Shared fixtures now lock public names, accessor
  behavior, second-arity parse behavior, and the existing seeded XML corpus.
* **Completed locally:** align ``clojure.core/merge`` with Clojure's observable
  reduction-through-``conj`` edge behavior for non-map first arguments, and
  tighten map ``conj`` so arbitrary sequential pairs such as lists and strings
  are rejected while vector-like pairs remain accepted. A shared fixture locks
  ordinary map merge, permissive first-argument reduction, map-entry rejection
  boundaries, and a seeded merge corpus.
* **Completed locally:** deepen ``clojure.pprint/code-dispatch`` parity by
  adding the portable Clojure formatter-table families for hold-first forms,
  ``if``/``when`` variants, ``condp``, ``with-local-vars``, ``locking``,
  ``struct``/``struct-map``, member access forms, and readable ``fn*``
  anonymous-function expansions. The shared ``pprint`` fixture now includes
  direct formatter-family cases plus a deterministic generated corpus across
  stable margins.
* **Completed locally:** align direct ``clojure.core.server/prepl`` and
  ``io-prepl`` with Clojure's conventional ``user`` default namespace, preserve
  namespace transitions and ``:repl/quit`` behavior through a shared fixture,
  retain generated isolated namespaces for loopback socket connections, accept
  string ports in ``remote-prepl`` like Clojure, and raise the pREPL socket
  backlog for concurrent-client stress.
* **Completed locally:** lock ``clojure.zip`` semantic parity with a shared
  fixture covering exact public names, vector/sequence/custom zipper navigation,
  edits, removals, generated traversal/edit/removal corpora, and the Clojure
  singleton ``seq-zip`` removal error boundary. Basilisp now normalizes zipper
  right-sibling state and no longer turns that boundary into a silent ``nil``.
* **Completed locally:** lock ``clojure.walk`` semantic parity with a shared
  fixture covering the required public names, replacement helpers, key
  transforms, traversal order, ``macroexpand-all``, metadata, sorted map/set
  preservation, and a deterministic generated nested-data corpus. Basilisp now
  reconstructs maps and sets through ``empty``/``into`` so walking preserves
  sorted collection behavior instead of coercing those values to hash
  collections.
* **Completed locally:** lock ``clojure.set`` semantic parity with a shared
  fixture covering the required public names, zero-arity ``union``, rejected
  zero-arity ``intersection``/``difference``, sorted set and metadata
  preservation across set operations, relational helpers, empty joins,
  Clojure's first-row shared-key rule for natural joins, and a generated set
  operation/join corpus.
* **Completed locally:** lock ``clojure.template`` parity with a shared
  fixture covering the exact public surface, ``apply-template`` replacement
  boundaries, duplicate binding handling, short/long value lists, quoted-form
  walking, ``do-template`` macroexpansion, incomplete group dropping, and
  generated apply/macroexpansion corpora.
* **Completed locally:** lock ``clojure.edn`` reader parity with a shared
  fixture covering the required public names, ``read-string`` EOF/trailing-form
  behavior, comments, discard forms, numeric/symbol/keyword/character forms,
  namespaced maps, reader constants, custom/default tagged readers, stream
  reads, rejection boundaries, and a generated nested EDN corpus. Basilisp-only
  EDN writer support is covered by local generated read/write round trips.
* **Completed locally:** lock ``clojure.datafy`` parity with a shared fixture
  covering the required public names, default ``datafy`` identity behavior,
  provenance metadata keys, unchanged identity results, ``nav`` delegation,
  ordinary collection navigation defaults, Clojure-compatible ``nil`` ``nav``
  rejection, and a generated object-to-data corpus.
* **Completed locally:** lock ``clojure.core.rrb-vector`` parity with a shared
  fixture covering the exact public surface, constructors, ``catvec`` and
  ``subvec`` rejection boundaries, metadata preservation/drop boundaries for
  empty and non-empty concatenation, source metadata preservation for slicing,
  and generated concatenation/slicing corpora.
* **Completed locally:** lock the portable ``clojure.tools.macro`` surface with
  a shared fixture covering local macro expansion, symbol macro expansion,
  lexical binding protection, global symbol macros, templates,
  ``name-with-attributes``, qualified-name rejection, and a generated
  symbol-macro expansion corpus.
* **Completed locally:** lock the portable ``clojure.test.check`` contract with
  a shared fixture covering root/generator/property/result/rose-tree public
  names, primitive and collection generator invariants, combinator behavior,
  constructor helpers, Clojure namespace result-data keys, quick-check passing
  and failing result shapes, exception counterexamples, generated property
  corpora, auxiliary rose-tree helpers, ``big-ratio`` and
  ``lazy-random-states``, and the portable ``clojure-test`` option/reporting
  surface.
* **Completed locally:** lock the broader standard namespace public-surface
  audit across already-ported namespaces. ``scripts/standard_namespace_surface_matrix.py``
  compares each configured Clojure/Basilisp namespace pair in one process per
  runtime, includes the contrib dependencies needed for the audited surface,
  and fails on any unclassified missing Basilisp public Var. The only classified
  missing symbols are generated/JVM-hosted reflection and logging artifacts;
  Basilisp extensions remain reported but non-failing.
* **Completed locally:** make rewritten standard ``clojure.*`` namespaces
  globally findable by their requested names. Source-compatible requires such
  as ``clojure.string``, ``clojure.core.server``, ``clojure.stacktrace``,
  ``clojure.reflect``, and the portable ``clojure.java.*`` aliases now support
  ``find-ns``/``ns-publics`` through the original Clojure namespace symbol
  instead of only through the backing ``basilisp.*`` implementation name.

5. Compiler, Runtime, And Debugging
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Correctness and debuggability should be treated as product features. A fork can
move faster only if failures are understandable and regression tests stay
focused.

Initial targets:

* macro definitions in ``try`` blocks (`#1086 <https://github.com/basilisp-lang/basilisp/issues/1086>`_)
* closure capture in ``loop`` (`#990 <https://github.com/basilisp-lang/basilisp/issues/990>`_)
* compile-time method signature verification (`#949 <https://github.com/basilisp-lang/basilisp/issues/949>`_)
* custom Basilisp tracebacks (`#461 <https://github.com/basilisp-lang/basilisp/issues/461>`_)
* coverage.py plugin (`#318 <https://github.com/basilisp-lang/basilisp/issues/318>`_)

Completed locally:

* macro definitions in nested compiler bodies, including ``try``/``catch``/``finally``
* ``loop`` closure capture across eager, lazy, nested, and large-loop cases
* compile-time inherited method signature diagnostics for ``deftype`` and
  ``reify``, including metadata suppression for known-safe mismatches
* clojure-test-suite residual classification guardrails: every excluded external
  core test file is assigned to an explicit stale-expectation cluster and backed
  by a local conformance fixture before CI can ignore it
* namespace import-order stability: requiring a child namespace such as
  ``basilisp.core.memoize`` no longer lets Python's parent-module submodule
  assignment overwrite an existing parent namespace Var such as
  ``basilisp.core/memoize`` used by direct-linked code
* rewritten Clojure namespace identity: standard namespace rewrites now install
  global namespace-name aliases, so ``find-ns`` and ``ns-publics`` work with the
  original ``clojure.*`` symbol while ``all-ns`` remains a list of real loaded
  Basilisp namespaces rather than duplicate alias entries

Near-term deliverable:

* improve source mapping, traceback output, and coverage support before making
  broad language changes

6. Python-Native Extensions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is where a fork should become more than a compatibility project. Python is
not only the host runtime; it is the ecosystem Basilisp users will reach for.

Candidate investments:

* first-class ``asyncio`` interop for coroutines, tasks, futures, queues, and
  async iterables
* richer conversions between Basilisp data and Python mappings, sequences,
  dataclasses, attrs classes, Pydantic models, NumPy arrays, Pandas frames,
  Polars frames, and PyArrow tables
* stronger function signature and keyword argument interop
* metadata-driven Python type annotations where the compiler can safely emit
  them
* Jupyter/IPython integration
* Python debugger, traceback, and coverage integration
* multiprocessing and thread/process pool helpers that fit Python's runtime
  model better than JVM-style STM

Near-term deliverable:

* choose one Python-native integration area and make it excellent rather than
  scattering thin wrappers across the ecosystem

Operating Principles
--------------------

* Keep compatibility changes small, reproduced, tested, and traceable to a
  documented gap.
* Prefer public Clojure behavior over internal implementation details.
* Prefer Python-native behavior when JVM semantics do not map cleanly.
* Maintain a compatibility matrix instead of relying on memory or anecdotes.
* Treat issue fixes, parity work, and fork-only experiments as separate patch
  queues.
* Document intentional incompatibilities in the same place as missing features.

First Milestone
---------------

The first milestone should establish the fork's operating system:

* a clean patch queue of reproduced issue fixes
* a generated core parity matrix
* a prioritized project tooling design
* focused ``basilisp.test`` compatibility improvements
* one Python-native integration spike

After that, the fork can make a better decision about branding, release
cadence, and whether it is still best understood as a downstream Basilisp fork
or as a new Python-hosted Clojure-family language.
