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
  The Clojure command defaults through ``CLOJURE_COMMAND``, native ``clojure``,
  or WSL on Windows, pins the default JVM runtime to Clojure 1.12.4, and the
  script exits non-zero if any Clojure public Var is absent from Basilisp so it
  can be used as a real gate rather than a report-only helper.
* use ``scripts/differential_conformance.py`` for portable behavioral fixtures.
  By default it evaluates every ``tests/conformance/*_cases.cljc`` source file
  in Clojure and Basilisp and compares parsed EDN, so map print order and other
  non-semantic formatting cannot hide or create a compatibility difference. Its
  default Clojure command pins the JVM runtime to Clojure 1.12.4 plus the
  audited contrib dependencies used by the fixture corpus.
  For full-corpus proof runs, use ``--disable-basilisp-ns-cache`` when the
  result must be independent from existing ``.lpyc`` state, and use
  ``--shard-count``/``--shard-index`` to split the stable fixture order across
  resumable CI jobs or local batches.
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
  arguments for CI. Use ``--verify-evidence`` to run those named fixtures
  through the differential harness before trusting the exclusions.
* use ``scripts/library_acceptance.py`` for a source-level, multi-file library
  proof. It executes the library-owned ``run.cljc`` test entrypoint in Clojure
  and Basilisp, compares the final EDN summary, and rejects a stale checked-in
  manifest. Its default Clojure command also pins Clojure 1.12.4. Use ``--all``
  to run every checked-in acceptance library in stable order; broad proof runs
  should add ``--disable-basilisp-ns-cache`` and may use
  ``--shard-count``/``--shard-index`` to split the accepted source corpus without
  depending on stale ``.lpyc`` artifacts. The initial
  ``tests/acceptance/portable_library`` fixture exercises standard ``string``,
  ``set``, ``walk``, collection, transducer, exception, and ``clojure.test``
  behavior using only documented ``:clj``/``:lpy`` namespace substitutions.
  ``tests/acceptance/upstream/cognitect-anomalies`` is the first pinned
  upstream snapshot; run it with ``--library-root`` to prove the unchanged
  source's public spec contract in both runtimes.
  ``basilisp.tools.cli`` is the first substantial upstream port: it retains a
  pinned ``clojure/tools.cli`` source snapshot, a minimal Python-hosted port,
  and a shared parsing/defaults/errors/subcommand acceptance contract. The
  checked-in upstream acceptance corpus also covers ``math-combinatorics``,
  ``medley``, ``tools-macro``, ``algo-generic``, ``algo-monads``,
  ``core-unify``, ``core-cache-memoize``, ``core.async``, ``data.csv``,
  ``core.match``, and ``tools.namespace``. The
  ``algo-generic`` proof exercises host-adapted multimethod dispatch across
  comparison, arithmetic, collection, functor, future/delay, and math-function
  contracts, and is pinned to ``clojure/algo.generic`` revision
  ``660b62b2fd84ed4c7383e2263f1fae039a5f5435``. The ``algo-monads`` proof
  exercises source-level macro-generated monadic functions, comprehension
  conditionals, writer/state/reader/continuation monads, and transformer
  contracts, and is pinned to ``clojure/algo.monads`` revision
  ``cc1fdb069049245a1226064c2fa55a65e72810a0``. The ``core-unify`` proof
  exercises symbolic unification, wildcard/range variables, substitution,
  factory-generated unifiers, occurs-check failures, and order-explicit map
  pattern unification, and is pinned to ``clojure/core.unify`` revision
  ``cbcf559abc86e30fbad83acdb0f8ab787379ad16``. The
  ``core-cache-memoize`` proof loads checked-in upstream ``data.priority-map``,
  ``core.cache``, and ``core.memoize`` snapshots on the JVM side while
  exercising Basilisp's production cache and memoize namespaces; it locks
  portable stateful cache policy, memoization snapshot/manipulation,
  constructor, and protocol interop without claiming JVM ``SoftReference``
  support. The ``core.async`` proof uses the published
  ``org.clojure/core.async`` 1.9.865 artifact on the JVM side and Basilisp's
  production ``clojure.core.async`` facade on the Basilisp side; it locks
  multi-file source-level usage of ``go``/``go-loop`` parking, ``alt!``,
  timeout selection, pipelines, collection/channel combinators, finite mult/pub
  routing, and a deterministic generated parking stress corpus while keeping
  direct IOC state-machine integration explicitly outside the current contract.
  The ``data.csv`` proof uses the published ``org.clojure/data.csv`` 1.1.0
  artifact on the JVM side and Basilisp's production ``clojure.data.csv`` alias
  on the Basilisp side; it locks multi-file source-level read/write workflows,
  reader/writer interop, delimiter/quote/newline options, scalar row coercion,
  and deterministic generated round trips with commas, quotes, CR/LF text, and
  custom separators.
  The ``core.match`` proof uses the published ``org.clojure/core.match`` 1.1.1
  artifact on the JVM side and Basilisp's production ``clojure.core.match``
  alias on the Basilisp side; it locks the user-facing portable macro subset
  across literals, bindings, vector/map/seq patterns, rest patterns,
  application patterns, as-patterns, ``matchv``, ``matchm``, ``match-let``, and
  no-match boundaries while keeping JVM/CLJS implementation helper namespaces
  outside the current contract.
  The ``tools.namespace`` proof uses the published
  ``org.clojure/tools.namespace`` 1.5.0 artifact on the JVM side and Basilisp's
  production ``clojure.tools.namespace`` aliases on the Basilisp side; it locks
  selected public facades, namespace parsing, dependency graphs, tracker
  ordering, generated acyclic graph stress cases, file/dir/JAR source
  discovery, and namespace move/rewrite boundaries. The acceptance manifest is
  intentionally classified as host-adapted because the fixture uses Java
  filesystem/JAR setup on the JVM side and Python filesystem/ZIP setup on the
  Basilisp side while emitting normalized cross-runtime results.

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
  differential fixtures. The priority-map semantic follow-up now directly
  covers ``priority-map-keyfn-by`` construction/update behavior, raising
  ``clojure.data.priority-map`` direct semantic fixture coverage to 100.0%, with
  local seeded stress checks for key-function plus custom-comparator ordering.
* **Completed locally:** add the first ``clojure.core.async`` facade tranche
  for the non-``go`` subset: Clojure-shaped buffers and ``chan``, close and
  non-blocking operations, awaitable/callback ``put!`` and ``take!``,
  ``alts!``, ``timeout``, ``pipe``, and Clojure-ordered ``pipeline``. Parking
  forms remain absent. The follow-up fixture now compares the
  implemented subset against JVM ``core.async`` for buffers, close/drain, nil
  rejection, channel transducers, selection, timeout, pipe, pipeline order,
  pipeline variants, and the non-``go`` collection/channel combinators
  ``to-chan!``, ``onto-chan!``, ``merge``, ``split``, ``take``, ``into``,
  ``reduce``, ``transduce``, ``promise-chan``, ``to-chan``, ``to-chan!!``,
  ``onto-chan``, ``onto-chan!!``, ``map``, ``partition``, ``partition-by``,
  ``unique``, ``unblocking-buffer?``, ``map<``, ``map>``, ``filter<``,
  ``filter>``, ``remove<``, ``remove>``, ``mapcat<``, and ``mapcat>``.
  The follow-up local
  tranche now adds
  task-backed routing combinators ``mult``,
  ``tap``, ``untap``, ``untap-all``, ``pub``, ``sub``, ``unsub``,
  ``unsub-all``, ``mix``, ``admix``, ``unmix``, ``unmix-all``, ``toggle``, and
  ``solo-mode`` plus the routing protocol helper surface ``Mux``, ``Mult``,
  ``Pub``, ``Mix``, ``muxch*``, ``tap*``, ``untap*``, ``untap-all*``, ``sub*``,
  ``unsub*``, ``unsub-all*``, ``admix*``, ``unmix*``, ``unmix-all*``,
  ``toggle*``, and ``solo-mode*`` with shared JVM fixtures. The stacked
  blocking-bridge tranche
  adds ``<!!``, ``>!!``, ``alts!!``, ``alt!!``, ``do-alt``, ``thread``,
  ``thread-call``, and ``io-thread`` with explicit same-owner-loop rejection
  for blocking channel calls. ``alt!!`` expands to the existing ``alts!!``
  bridge. The stacked helper-publics tranche adds ``fn-handler``, ``do-alts``,
  and ``defblockingop`` with JVM fixtures for the immediate/enqueued
  ``do-alts`` contract and macro metadata. The stacked pipeline-variants tranche
  adds ``pipeline-blocking`` and ``pipeline-async`` with ordered fan-out,
  ``close?`` behavior, early destination-close handling, and JVM fixtures.
  The stacked channel-transducer tranche adds ``chan`` xform/ex-handler support
  with put-time transforms, stateful completion flush, fan-out, early
  transducer completion, nil-output rejection, local seeded stress, and JVM
  fixtures. The stacked minimal-go tranche closes the remaining
  ``clojure.core.async`` public-surface gap with coroutine-backed ``go``,
  ``go-loop``, ``<!``, ``>!``, and ``alt!`` plus an explicit ``ioc-alts!``
  rejection boundary. This gives public surface parity for ordinary portable
  examples while full Clojure IOC/state-machine parity remains a deeper
  compiler project. The follow-up hardening tranche now adds shared JVM
  fixtures for closed-channel takes, puts to closed channels, timeout
  interaction, nested ``alt!`` choices, close/result races, and
  exception-driven result-channel close behavior, plus local runtime tests for
  current-loop ``go`` scheduling and same-owner-loop blocking rejection inside
  ``go``. The stream-helper hardening follow-up fixes sentinel collisions in
  ``partition-by`` and ``unique`` when user data equals the old internal
  keyword sentinel, and adds JVM fixtures for zero-source ``map`` close
  behavior plus Clojure's current batch semantics when one mapped source closes
  while another source is still idle. It also adds a generated mixed-value
  stream-helper corpus for ``map``, ``partition``, ``partition-by``, and
  ``unique``, extends the source-level ``core.async`` acceptance workflow with
  those helpers, and removes a race in the shared ``mix`` fixture by allowing
  toggle signals to reach the routing loop before asserting muted/paused
  output.
* **Completed locally:** deepen ``clojure.string`` semantic coverage across the
  full portable public surface. Shared fixtures now directly exercise
  predicates, case conversion, prefix/suffix/inclusion checks, joins, reverse,
  trims, indexes, ``split`` limits/trailing-empty behavior, ``split-lines``
  newline boundaries, literal/regex replacements, replacement functions,
  ``$1`` group replacements, ``re-quote-replacement``, and ``escape``. This
  tranche raised direct semantic fixture coverage for ``clojure.string`` to
  70.0% and fixed Clojure-compatible ``last-index-of``, ``split``,
  ``split-lines``, and regex replacement quoting semantics while preserving
  Python string-keyed ``escape`` maps and non-BMP codepoints.
* **Completed locally:** deepen ``clojure.data.json`` serialization and
  parser-boundary semantics. Shared fixtures now directly cover single stream
  reads, nested ``:value-fn`` omission, extra-data reader suffixes, EOF value
  handling, malformed token rejection, JavaScript line/paragraph separator
  escaping, raw JS separator round trips, raw Unicode/slash output options,
  pretty-print round trips, ``:key-fn`` write transforms, and nested write
  ``:value-fn`` filtering. Local regression tests mirror the adversarial
  option matrix so escaping and callback semantics stay locked near the
  Python-hosted JSON backend.
* **Completed locally:** deepen ``clojure.data.csv`` parser/writer boundary
  semantics. Shared fixtures now directly cover char and integer delimiters,
  delayed writer option coercion, invalid newline ``"null"`` output parity,
  quote predicate extremes, CRLF round trips, scalar coercion for nil/booleans/
  numbers/keywords/symbols, empty-record handling, embedded CR/LF/CRLF cells,
  and custom separator/quote round trips. Local regression tests mirror the
  adversarial option and row-shape matrix so Python ``csv`` backend behavior
  stays aligned with Clojure ``data.csv``.
* **Completed locally:** deepen ``clojure.data.codec.base64`` decoder and
  transfer-boundary semantics. Shared fixtures now directly cover destination
  tail preservation for ``encode!``/``decode!``, high-byte decoder table
  rejection, permissive low-ASCII invalid bytes, ignored trailing partial high
  bytes, offset high-byte rejection, and split-buffer versus same-buffer
  streaming failure output. Basilisp now matches Clojure ``data.codec``'s
  bounded decoder table instead of treating every non-alphabet byte up to 255 as
  zero bits. Local regression tests mirror these cases plus seeded offset and
  in-place round trips.
* **Completed locally:** close portable constructor/protocol gaps in
  ``clojure.core.cache``, ``clojure.core.memoize``, and
  ``clojure.core.protocols``, and add the standard ``clojure.core.reducers``
  import path. Shared fixtures now cover cache/memoize generated constructors,
  core protocol reduction helpers, reducers stress cases through the standard
  namespace, and explicit JVM-boundary classification.
* **Completed locally:** close the remaining deprecated
  ``clojure.tools.namespace`` root facade names by mapping classpath discovery
  to Basilisp's Python import path, including directories and ZIP/JAR archives.
* **Completed locally:** close ``clojure.tools.reader``,
  ``clojure.tools.reader.default-data-readers``, ``clojure.tools.reader.edn``,
  ``clojure.tools.reader.impl.commons``,
  ``clojure.tools.reader.impl.errors``,
  ``clojure.tools.reader.impl.inspect``, ``clojure.tools.reader.impl.utils``,
  and ``clojure.tools.reader.reader-types`` public surface parity. Shared
  fixtures now cover dynamic Vars, ``map-func``, reader-type
  constructors/coercers, metadata merging, EDN-only reads, default ``inst`` and
  ``uuid`` data readers, and character-returning ``read-char`` behavior.
  Plain pushback readers now correctly remain non-indexing while
  ``indexing-push-back-reader`` and source-logging readers expose line/column
  metadata.
* **Completed locally:** close ``clojure.tools.logging.impl`` and the portable
  ``clojure.tools.logging`` dynamic Var/factory surface over Python logging.
  Java backend selectors are documented no-ops; the remaining JVM proxy-class
  public Var is treated as an implementation artifact.
  The logging semantic follow-up now also locks the macro arity boundary where
  a throwable supplied as the only print-style argument is a normal message,
  while throwable-plus-message uses the throwable slot. Shared and local
  adversarial tests cover the root and readable logging macros, readable
  literal-string versus runtime-string rendering, and disabled optimized paths
  that must not realize message expressions. The contrib namespace audit
  follow-up adds ``clojure.tools.logging.readable`` to the standard surface and
  semantic coverage matrix, implements the missing public ``spyf`` macro, and
  locks all readable macro Vars through direct shared fixture calls.
* **Completed locally:** close ``clojure.spec.alpha``,
  ``clojure.spec.test.alpha``, and ``clojure.spec.gen.alpha`` public namespace
  surface gaps. Shared fixtures now cover protocol/helper names, registry and
  explain-data entrypoints, regex implementation helpers, and portable
  ``spec.test.alpha`` summary/symbol helpers. Remaining spec work is semantic
  depth for generation edge cases and explicit Python model adapters, not
  missing public names.
* **Completed locally:** deepen ``clojure.spec.alpha`` semantic coverage across
  the portable standard surface. Shared fixtures now directly exercise core
  spec creation, registry lookup, composition, collection specs, regex specs,
  numeric/instant range specs, assertions/explain helpers, generator and
  ``fspec`` contracts, protocol helpers, and safe implementation-helper
  entrypoints. The follow-up now directly covers the remaining public control
  Vars, protocol Vars, invalid sentinel, ``explain``, ``fdef*``, and
  ``get-fspec``, raising direct semantic fixture coverage for
  ``clojure.spec.alpha`` to 100.0%. Fixes include ``s/abbrev`` public
  symbol/list abbreviation parity and Clojure-shaped ``explain-data`` maps with
  top-level ``::spec`` and ``::value`` keys. The adversarial semantic follow-up
  now covers conformer chaining through ``s/and``, regex repeat backtracking
  across later ``s/cat`` branches, ``s/alt`` branch-order behavior,
  ``keys*`` permutation/unform contracts, and nested regex explain paths. It
  fixed reverse unforming for ``s/and``, greedy regex repeat backtracking, and
  tagged child ``:path`` values in regex explain data.
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
* **Completed locally:** deepen ``clojure.instant`` leap-second and offset
  boundary parity. Shared fixtures now directly cover optional offsets after
  hour/minute forms, fractional nanosecond truncation, offset extremes, valid
  leap-second normalization through Date/Calendar/Timestamp paths, and invalid
  leap-second rejection outside minute ``59``. Basilisp now normalizes
  Clojure-valid ``second=60`` instants before constructing Python datetime
  values, preserving Calendar offsets and Timestamp nanoseconds.
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
  boundaries, and a seeded merge corpus. The residual follow-up now hardens
  this proof across persistent ``conj``, ``merge``, transient ``conj!``,
  ``nil``, maps, map entries, nested vector-pair keys, character/string key
  distinction, invalid lists/strings/short vectors/long vectors, and generated
  mixed-input cases; no additional runtime change was required.
* **Completed locally:** deepen ``clojure.core`` transducer and reduction
  boundary parity. ``transduce`` now runs reducing-function completion for
  empty and short-circuited inputs, and ``sequence`` no longer reinitializes
  transducers per item, drops terminal completion output, or crashes when
  ``halt-when`` returns a scalar reduced value. The shared core-semantics
  fixture now locks empty/reduced ``transduce`` completion, ``sequence``
  completion flushing, ``halt-when`` boundaries, ``partition-all`` final chunks,
  multi-collection ``sequence``, and a seeded transducer corpus across
  ``sequence``, ``into``, and ``transduce``. The adversarial follow-up now also
  locks custom ``halt-when`` return-function ordering: the wrapped reducing
  function's completion runs before ``retf`` observes the halted result, and it
  is not run a second time after reduced short-circuiting.
* **Completed locally:** deepen ``clojure.pprint/code-dispatch`` parity by
  adding the portable Clojure formatter-table families for hold-first forms,
  ``if``/``when`` variants, ``condp``, ``with-local-vars``, ``locking``,
  ``struct``/``struct-map``, member access forms, and readable ``fn*``
  anonymous-function expansions. The shared ``pprint`` fixture now includes
  direct formatter-family cases plus a deterministic generated corpus across
  stable margins. The exact-width follow-up now ports Clojure's recursive XP
  section processing, aligns ``if``/``when`` and ``condp`` boundary newline
  decisions, lets ``try``/``catch``/``finally`` fall through to ordinary
  code-list printing like Clojure, and preserves strict ``:fill`` subsection
  boundaries.
* **Completed locally:** deepen ``clojure.pprint`` semantic coverage beyond
  code dispatch. Shared fixtures now directly exercise dynamic print Vars,
  ``get-pretty-writer``, ``fresh-line``, ``pprint-indent``, ``pprint-newline``,
  ``pprint-tab``'s Clojure-compatible direct rejection, ``print-length-loop``,
  ``set-pprint-dispatch``, ``pp``, and ``write`` option contracts. This tranche
  raised direct semantic fixture coverage for ``clojure.pprint`` to 65.0% and
  fixed direct ``fresh-line`` fallback behavior, public ``pprint-tab`` parity,
  and ``write`` rendering so it honors base/radix/namespace options without
  appending ``pprint``'s trailing newline. The adversarial follow-up now covers
  combined ``write`` options, metadata controls, namespace suppression, nested
  data across narrow margins, and radix-prefixed negative integer/ratio
  rendering. It fixed simple-dispatch radix output so negative non-decimal
  integers and ratio numerators match Clojure's printed source shape while
  denominators remain unprefixed. The exact-margin follow-up now also flushes
  the pretty-writer buffer before ``pprint`` emits its trailing newline, so the
  newline cannot participate in width decisions and force premature internal
  breaks on Windows-style line endings. The source-resource omission hardening
  follow-up raises direct semantic fixture coverage for ``clojure.pprint`` to
  100.0% through the public namespace and locks the bundled implementation
  families behind it: adversarial ``print-table`` missing/nil cells, inferred
  column behavior, mixed-width rows, ``cl-format`` nested iteration, case
  conversion, argument jumps, iteration escapes, conditional selection
  boundaries, plural suffixes, English cardinal/ordinal words, new/old Roman
  numerals, and format error boundaries. The ``cl-format`` directive
  adversarial follow-up now locks radix directives, comma grouping,
  sign-prefixing, character names, ``~A``/``~S`` padding, justification,
  recursive ``~?`` indirection, fresh-line boundaries, standalone ``~_``
  rejection, and absolute/relative ``~T`` tabulation. It fixes the relative
  ``~@T`` tab-stop calculation so already-aligned positions no longer receive
  an extra tab increment.
* **Completed locally:** align direct ``clojure.core.server/prepl`` and
  ``io-prepl`` with Clojure's conventional ``user`` default namespace, preserve
  namespace transitions and ``:repl/quit`` behavior through a shared fixture,
  retain generated isolated namespaces for loopback socket connections, accept
  string ports in ``remote-prepl`` like Clojure, and raise the pREPL socket
  backlog for concurrent-client stress. The diagnostics follow-up now treats
  ``read+string``'s ``[nil ""]`` result as EOF instead of repeatedly evaluating
  ``nil``, and locks local ``io-prepl`` tap serialization plus value-formatter
  failure events as structured ``:print-eval-result`` diagnostics. nREPL eval
  errors now use the same top-level ``:execution`` diagnostic phase while
  preserving compiler/read-specific phase and source data in the normalized
  diagnostic payload.
* **Completed locally:** lock ``clojure.zip`` semantic parity with a shared
  fixture covering exact public names, vector/sequence/custom zipper navigation,
  edits, removals, generated traversal/edit/removal corpora, and the Clojure
  singleton ``seq-zip`` removal error boundary. Basilisp now normalizes zipper
  right-sibling state and no longer turns that boundary into a silent ``nil``.
  The semantic-depth follow-up now directly covers ``left``, ``make-node``, and
  ``xml-zip``, raising direct semantic fixture coverage for ``clojure.zip`` to
  100.0%, with local seeded stress checks for sibling navigation, vector/custom
  node reconstruction, and XML text/element editing.
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
  The semantic-depth follow-up now directly marks the Basilisp-only
  ``EDNEncodeable``/``write``/``write*``/``write-string`` extension surface
  under reader conditionals, raising direct semantic fixture coverage for
  ``clojure.edn``/``basilisp.edn`` to 100.0% without expanding the shared
  Clojure API claim.
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
  a shared fixture covering the root, ``generators``, ``properties``,
  ``results``, ``random``, ``rose-tree``, and ``clojure-test`` public
  namespaces, plus the support namespaces
  ``clojure.test.check.impl``,
  ``clojure.test.check.clojure-test.assertions``, and the empty
  ``clojure.test.check.clojure-test.assertions.cljs`` hook. The audited
  surface is now part of the standard namespace matrix, with direct semantic
  fixture coverage at 100.0% for every configured ``clojure.test.check``
  namespace. Fixtures cover primitive and collection generator invariants,
  combinator behavior, constructor helpers, the ``Result`` protocol, Clojure
  namespace result-data keys, quick-check passing and failing result shapes,
  exception counterexamples, generated property corpora, auxiliary rose-tree
  helpers, ``big-ratio``, ``lazy-random-states``, portable ``clojure-test``
  option/reporting helpers, assertion-result reporting, and the public
  wall-clock millisecond helper. The upstream random namespace's generated JVM
  ``ThreadLocal`` proxy Var is classified as a non-portable implementation
  artifact.
* **Completed locally:** lock the broader standard namespace public-surface
  audit across already-ported namespaces. ``scripts/standard_namespace_surface_matrix.py``
  compares each configured Clojure/Basilisp namespace pair in one process per
  runtime, includes the contrib dependencies needed for the audited surface,
  and fails on any unclassified missing Basilisp public Var. The remaining
  classified non-portable artifacts are upstream generated JVM proxy Vars;
  Basilisp extensions remain reported but non-failing.
* **Completed locally:** add ``clojure.data.xml``,
  ``clojure.data.xml.event``, and ``clojure.data.xml.tree`` to the audited
  standard/contrib public-surface matrix against ``org.clojure/data.xml``
  ``0.2.0-alpha11`` and deepen their semantic proof. Shared fixtures now cover
  QName URI helpers, URI symbol/file encoding, namespace metadata helpers,
  aggregate namespace discovery, event map constructors, end-element event
  tags, CDATA coalescing boundaries, parse/emit/indent round trips, and a
  deterministic generated tree corpus. Basilisp now exposes the missing
  portable public helpers including ``element*``, ``parse-qname``,
  ``alias-uri``, ``uri-file``, ``find-xmlns``, ``aggregate-xmlns``,
  ``event/element-nss*``, and the event ``map->`` constructors.
* **Completed locally:** make rewritten standard ``clojure.*`` namespaces
  globally findable by their requested names. Source-compatible requires such
  as ``clojure.string``, ``clojure.core.server``, ``clojure.stacktrace``,
  ``clojure.reflect``, and the portable ``clojure.java.*`` aliases now support
  ``find-ns``/``ns-publics`` through the original Clojure namespace symbol
  instead of only through the backing ``basilisp.*`` implementation name.
* **Completed locally:** deepen the host-bound ``clojure.java.process`` and
  ``clojure.java.shell`` compatibility aliases. Shared fixtures now cover
  process stdin pipe writes, ``:err :stdout`` merging, ``:out``/``:err``
  discard redirects, append file redirects, explicit working directories,
  non-zero ``exec`` rejection, cleared-environment lookup, explicit stream
  encodings, shell dynamic binding precedence, explicit shell option override,
  non-throwing shell non-zero exit maps, and shell stdin replay. Basilisp now
  returns empty readable stdout/stderr streams when Python's subprocess object
  has no concrete pipe because output was discarded, inherited, or merged,
  matching Clojure's non-nil process stream shape more closely. Local alias
  tests also stress repeated shell stdin/env/dir option combinations.
* **Completed locally:** deepen the host-bound ``clojure.java.io``
  compatibility alias. Shared fixtures now cover direct factory reads/writes,
  sequential delete return contracts, append versus overwrite behavior,
  existing-parent and newly-created-parent ``make-parents`` return values,
  binary stream round trips, relative URL and absolute-relative-path rejection,
  file-URL slurping, path/string copy behavior, and resource lookup through a
  temporary JVM classloader or isolated Python import path. Basilisp now treats
  existing parent directories as a non-error ``make-parents`` result and
  returns ``true`` from two-argument ``delete-file`` after a successful delete,
  matching Clojure's observable return contracts. Local alias/property tests
  lock these file-boundary behaviors and disable irrelevant Hypothesis timing
  deadlines around runtime initialization.
* **Completed locally:** lock the Clojure 1.12.4 bundled namespace inventory.
  ``scripts/standard_namespace_inventory.py`` classifies every bundled
  ``clojure.*`` source/resource entry as core-covered, surface-audited,
  source-resource-only, or legacy-source-audited. The tranche also implements the
  portable ``clojure.core.specs.alpha`` helper ``even-number-of-forms?`` and
  the empty ``clojure.uuid`` namespace, with shared differential fixtures for
  both. Later tranches moved the previously omitted UI/tooling namespaces into
  audited compatibility surfaces.
* **Completed locally:** add the portable ``clojure.main`` compatibility
  surface. Requires of ``clojure.main`` now rewrite to ``basilisp.main-compat``
  instead of colliding with Basilisp's Python ``basilisp.main`` CLI module.
  The tranche covers Clojure's public helper surface, reader sentinels,
  ``repl-read`` flow, option-driven ``repl`` hooks, ``with-read-known`` dynamic
  behavior, and deterministic error-string formatting with shared differential
  and local adversarial tests. JVM process entrypoint behavior remains owned by
  Basilisp's Python CLI. The semantic-depth follow-up now directly covers every
  audited public Var, including ``demunge``, ``err->msg``, ``ex-triage``,
  ``renumbering-read``, ``repl-caught``, ``repl-exception``, ``repl-prompt``,
  ``repl-requires``, ``report-error``, ``root-cause``, ``stack-element-str``,
  and the host-bound ``load-script``/``main`` entrypoints, raising direct
  semantic fixture coverage for ``clojure.main`` to 100.0%.
* **Completed locally:** add the Python-native ``clojure.java.browse``
  compatibility surface and the empty public ``clojure.java.browse-ui``
  namespace. ``browse-url`` uses a configured script when supplied and falls
  back to Python's ``webbrowser`` module, while preserving Clojure's
  ``*open-url-script*`` atom shape for source compatibility.
* **Completed locally:** add the ``clojure.java.javadoc`` REPL-helper surface.
  The port keeps Clojure's public dynamic Vars and local/remote registry update
  helpers, delegates browser opening through ``clojure.java.browse``, and uses
  Python class names for host documentation lookup when Java classes are not
  available.
* **Completed locally:** add ``clojure.test.junit`` XML reporter parity.
  ``basilisp.test.junit`` exposes Clojure's public reporter helpers, routes
  through Basilisp's existing ``clojure.test`` report hooks, emits deterministic
  JUnit-compatible XML, and fuzz-tests XML escaping for assertion messages and
  attributes. The adversarial semantic follow-up now also locks package/class
  splitting for empty and dotted boundaries plus exact generated XML rendering
  for pretty/non-pretty elements. Basilisp now preserves caller-supplied
  attribute order in ``start-element`` instead of imposing a preferred order.
* **Completed locally:** deepen ``clojure.test.tap`` reporter output parity.
  Shared fixtures now cover blank, internal-blank, and trailing-newline TAP
  diagnostics, nil plans, empty pass/fail messages, testing-context rendering,
  nil messages, string and map actual values, direct ``:error`` reports, and
  zero-count summaries. This tranche fixed ``print-tap-diagnostic`` so an empty
  diagnostic emits Clojure's ``#`` line instead of disappearing.
* **Completed locally:** add dependency-tooling compatibility facades for
  ``clojure.java.basis``, ``clojure.java.basis.impl``, ``clojure.repl.deps``,
  and ``clojure.tools.deps.interop``. The basis namespaces preserve the public
  delay/atom/update model for portable tooling. Clojure CLI tool invocation and
  dynamic dependency loading validate deterministic arguments and then raise
  explicit host-bound errors because Basilisp cannot mutate a JVM classpath
  from Python.
* **Completed locally:** add ``clojure.java.classpath`` compatibility after
  classpath resource discovery exposed it as an audited contrib namespace. The
  public surface now matches ``org.clojure/java.classpath`` 1.1.0 and maps JVM
  ``File``/``JarFile`` behavior onto Python ``pathlib.Path`` and
  ``zipfile.ZipFile`` values. Shared fixtures cover every public Var,
  URLClasspath protocol dispatch, nil-loader boundaries, jar suffix detection,
  jar entry enumeration, and classpath directory/jarfile filter shapes; local
  stress tests isolate ``sys.path`` mutation, duplicate removal, Windows file
  URL normalization, and generated archive entries.
* **Completed locally:** close the remaining ``clojure.reflect`` public-surface
  gap. ``basilisp.reflect`` now exposes Clojure-shaped ``Method``, ``Field``,
  and ``Constructor`` data records, public factory helpers, ``ClassResolver``,
  ``resolve-class``, and ``flag-descriptors``. Python reflection stays hosted by
  ``PythonReflector``; ``JavaReflector`` and ``AsmReflector`` preserve the
  public constructor/protocol shape and report an explicit JVM metadata
  boundary when used.
* **Completed locally:** deepen ``clojure.reflect`` semantic coverage across
  every audited public Var. Shared fixtures now directly exercise public record
  constructors and map factories, protocol Vars, ``typename``, ``resolve-class``,
  custom ``do-reflect`` dispatch, JVM reflector constructor shape, flag
  descriptors, and host-conditional ``reflect``/``type-reflect`` entrypoints.
  This tranche raised direct semantic fixture coverage for ``clojure.reflect``
  to 100.0% without weakening the JVM class-metadata boundary.
* **Completed locally:** add ``clojure.inspector`` compatibility. The namespace
  now requires successfully, exposes Clojure's public traversal/model surface,
  and provides Python-hosted TreeModel/TableModel-like proxy objects for
  ``tree-model``, ``old-table-model``, ``list-model``, ``table-model``, and the
  ``inspect*`` helpers. Basilisp intentionally returns non-graphical models
  instead of opening Swing windows.
* **Completed locally:** add a sequential compatibility layer for legacy
  ``clojure.parallel``. The Clojure 1.12.4 bundled source depends on obsolete
  ``jsr166y`` ForkJoin classes and fails to load on the verified JVM baseline,
  so Basilisp audits it from source rather than normal JVM namespace loading.
  The port preserves the public operation names and deterministic collection
  semantics for ``par`` pipelines, realization, aggregates, sorting, distinct,
  nil filtering, and consecutive duplicate filtering without promising actual
  parallel execution. The follow-up now adds a legacy source-publics verifier to
  ``scripts/standard_namespace_inventory.py``, enforces it in CI, and locks the
  source-compatible odd trailing operation boundary where upstream ``par`` uses
  ``partition 2`` and ignores the dangling option. The adversarial follow-up
  extends this proof to public arglists, empty/``nil`` realization, explicit
  unsupported operation failures, comparator aggregates, and generated
  ``:bound`` plus index/``*-with`` operation pipelines so the sequential
  compatibility layer cannot silently drift from its documented legacy-source
  boundary.
* **Completed locally:** close the bundled namespace inventory audit loop with
  a Basilisp-side require verifier. ``--verify-clojure`` continues to require
  every JVM-loadable audited namespace in Clojure, while ``--verify-basilisp``
  requires every runtime compatibility namespace in Basilisp, including the
  legacy-source-audited ``clojure.parallel``. Remaining source-resource
  omissions are explicitly excluded from both runtime require sets. The
  source-resource omission follow-up adds ``--verify-source-omissions``, which
  requires each exact Clojure implementation resource, verifies that it
  ``in-ns`` loads into its owning public namespace, and proves it does not
  create an independent public namespace. The main parity audit CI job now runs
  the Clojure, Basilisp, legacy-source, source-resource, and discovered-resource
  verification sides after installing Java and Clojure CLI. The
  ``--verify-discovered-resources`` gate enumerates ``clojure/*.clj`` and
  ``clojure/*.cljc`` entries from the active Clojure runtime jar and fails if a
  discovered namespace lacks an inventory classification, so future runtime-jar
  namespace additions cannot be silently omitted from parity triage.
* **Completed locally:** harden the public printer behavior that justifies
  treating bundled ``clojure.core-print`` as a source-resource omission rather
  than a separate requireable namespace. Shared fixtures now cover
  ``*print-meta*``/``*print-readably*`` metadata suppression, ``*print-dup*``
  metadata preservation, tag metadata shorthand, print length/level truncation,
  default and bound namespace-map rendering, escaped string and character
  printing, tagged literals, unreadable strings, set truncation, and a
  deterministic generated printable corpus. This tranche fixed Basilisp's
  lower-level representation helpers so metadata is suppressed when printing
  unreadably, while ``:tag`` metadata uses Clojure's ``^tag`` shorthand for
  vectors, maps, lists, sets, and symbols. The follow-up also aligns the root
  ``*print-namespace-maps*`` value with Clojure's default ``true`` so
  qualified-key maps print as namespace maps unless callers opt out.
* **Completed locally:** harden the public record/type behavior that justifies
  treating bundled ``clojure.core-deftype`` as a source-resource omission rather
  than a separate requireable namespace. Shared fixtures now cover
  ``defrecord`` nil-valued field and extension-map entries through
  ``contains?``, ``find``, ``seq``, ``into``, map constructors, seeded
  assoc/dissoc update corpora, plus portable ``deftype``/``reify`` protocol
  dispatch. Basilisp now returns strict booleans from generated record
  ``contains?`` methods and preserves nil-valued entries from generated record
  ``entry`` methods. The adjacent reader-conditional scanner now also handles
  vector-shaped map entries, so record reader forms continue round-tripping
  after direct nil-entry behavior is corrected.
* **Completed locally:** harden the public typed-vector behavior that justifies
  treating bundled ``clojure.gvec`` as a source-resource omission rather than a
  separate requireable namespace. Shared fixtures now cover ``vector-of``
  construction, equality/hash equivalence with ordinary vectors, boolean
  truthiness coercion, persistent ``conj``/``assoc``/``pop``/``subvec``
  behavior, metadata preservation and empty-vector metadata loss, transient
  rejection, invalid update boundaries, and a seeded persistent update corpus.
  Basilisp now returns a typed persistent vector wrapper from ``vector-of`` so
  later persistent updates continue to coerce or reject values like Clojure's
  primitive vectors, while still rejecting ``transient`` on typed vectors to
  match Clojure's non-editable ``Vec`` implementation.
* **Completed locally:** harden the public class-generation compatibility that
  justifies treating bundled ``clojure.genclass`` as a source-resource omission
  rather than a separate requireable namespace. Shared fixtures now cover direct
  ``gen-class`` no-op expansion across rich option shapes, ``ns`` form
  ``(:gen-class ...)`` clauses, ``with-loading-context`` execution, seeded
  option corpora, and invalid namespace-clause boundaries. Basilisp now rejects
  odd ``:gen-class`` namespace clauses during ``ns`` macroexpansion, matching
  Clojure's source grammar while preserving portable no-op behavior for valid
  class-generation declarations.
* **Completed locally:** harden the Java reflection implementation resource
  that justifies treating bundled ``clojure.reflect.java`` as a source-resource
  omission rather than a separate public namespace. Shared fixtures now cover
  the exact Java access flag descriptor table, ``Method``/``Field``/
  ``Constructor`` record map contracts, seeded member-record corpora,
  ``ClassResolver`` and custom ``Reflector`` protocol dispatch, JVM reflector
  shell satisfaction, and host-bound reflection boundaries. Basilisp now
  accepts plain ``(require 'clojure.reflect.java)`` only after
  ``clojure.reflect`` has been loaded, matching Clojure's implementation
  resource behavior while still creating no ``clojure.reflect.java`` namespace.
* **Completed locally:** begin the semantic-depth phase after public namespace
  parity reached a clean baseline. ``scripts/semantic_fixture_coverage.py``
  compares the audited public surface with direct ``alias/public-var`` uses in
  shared conformance fixtures so future tranches can target weak behavioral
  coverage instead of guessing from public-name matrices. This surfaced a real
  ``clojure.tools.logging/spy`` formatting mismatch, now fixed, and added direct
  macro/factory logging coverage plus a deterministic generated
  ``clojure.math.combinatorics`` corpus covering every public Var. It also
  added direct ``clojure.tools.cli`` fixtures for parsing, summaries, legacy
  ``cli``, generated option-token behavior, and current
  ``:subcommand :explicit`` semantics.
* **Completed locally:** deepen ``clojure.data/diff`` semantic coverage after
  the standard namespace surface and direct fixture coverage reached 100%.
  The shared fixture now hardens ``false`` and ``nil`` diff components, empty
  nested vectors/maps/sets, metadata-insensitive equality, record-vs-map
  boundaries, sorted-map comparison, sets containing collections, and a deeper
  generated structural corpus. This found and fixed a real Clojure gap:
  Basilisp no longer lets plain-map/record equality bypass ``clojure.data``'s
  map diff path, so record-vs-map and map-vs-record equal entries now preserve
  Clojure's seq-shaped diff result instead of returning the top-level equality
  vector.
* **Completed locally:** deepen ``clojure.tools.cli`` 1.4.256 option-boundary
  parity. The differential and namespace-surface harnesses now pin
  ``org.clojure/tools.cli`` to the same 1.4.256 upstream baseline as the
  checked-in acceptance port. Shared fixtures now lock deprecated
  ``:in-order`` handling, ``:subcommand :explicit`` and ``:implicit`` argument
  retention, ``:in-order``/``:subcommand`` conflict rejection,
  ``:default-fn``/``:no-defaults`` behavior, required ``:missing`` errors,
  custom ``:summary-fn`` output, and post-validation data shapes. Basilisp's
  tokenizer now stops at the first positional argument in subcommand mode,
  preserving the remaining argv exactly like upstream 1.4.256.
* **Completed locally:** harden full-corpus differential verification. The
  conformance harness now supports Basilisp-only namespace-cache disabling and
  stable fixture sharding, so complete parity proof runs no longer require
  manual batching or dependence on existing ``.lpyc`` cache state.
* **Completed locally:** harden the external ``clojure-test-suite`` residual
  gate. The residual classifier can now run its named evidence fixtures through
  the differential harness before emitting pytest ignores, and the CI workflow
  installs Java plus Clojure CLI before requiring that live proof.
* **Completed locally:** harden the numeric coercion residual evidence from the
  external ``clojure-test-suite`` audit. The shared numeric fixture now covers
  checked primitive integer boundary values plus host string/collection
  rejection. This found and fixed a concrete checked-cast gap:
  ``byte``/``short``/``int``/``long`` now range-check the original numeric value
  before truncating, matching Clojure instead of accepting fractional values
  that only become in-range after truncation.
* **Completed locally:** harden the character residual evidence from the
  external ``clojure-test-suite`` audit. The shared character fixture now
  directly covers the remaining residual collection names -- ``seq``,
  ``seqable?``, ``empty?``, ``not-empty``, ``fnext``, ``last``, realized
  ``remove``, ``reverse``, and ``set`` -- proving that first-class characters
  remain scalar values while strings retain collection behavior. Local
  adversarial tests also fuzz UTF-16 ``Character`` values at the Python runtime
  conversion layer so future changes cannot accidentally make characters
  iterable like one-character strings.
* **Completed locally:** harden the ``subs`` residual from the external
  ``clojure-test-suite`` audit. The shared character fixture now covers
  Clojure-style UTF-16 substring boundaries for omitted end, exact empty slices,
  negative and out-of-range indexes, reversed ranges, explicit ``nil`` start/end,
  booleans, infinities, and numeric index truncation. This found and fixed real
  gaps: explicit 3-arity ``nil`` end now rejects, and numeric indexes such as
  ``1.9`` and ``##NaN`` follow Clojure's primitive-int coercion behavior. The
  tranche also found and fixed transient wrapper argument interop that converted
  characters into host strings during ``into``/``conj!`` string reduction.
* **Completed locally:** harden the ``case`` numeric dispatch residual from the
  external ``clojure-test-suite`` audit. The shared ``case`` fixture now covers
  numeric family dispatch across integers, doubles, decimals, ratios, signed
  zero, NaN defaulting, grouped constants, generated dispatch tables, and
  duplicate-test boundaries. The expanded evidence is conformant with JVM
  Clojure, so no runtime change was made; the remaining upstream failures are
  stale ``:lpy`` expectations rather than a proven Basilisp behavior gap.
* **Completed locally:** harden the dedicated ``clojure.core`` public-surface
  gate. ``scripts/core_parity_matrix.py`` now discovers Clojure through
  ``CLOJURE_COMMAND``, native ``clojure``, or WSL on Windows, exits non-zero on
  missing Basilisp core publics, and runs in CI next to the semantic coverage,
  standard namespace surface, and namespace inventory audits.
* **Completed locally:** add direct ``clojure.core`` semantic fixture coverage
  triage. ``scripts/core_semantic_fixture_coverage.py`` now scans shared
  conformance fixtures for qualified core references, ``clojure.core`` aliases,
  unqualified core call heads, and narrow dynamic-Var value references. The
  audit runs in CI as an informational CSV rather than a 100% gate; the current
  purpose is to rank uncovered shared core Vars so the next behavior tranche is
  selected from evidence instead of public-surface guesswork.
* **Completed locally:** close the first core semantic tranche surfaced by that
  audit: primitive-array cast helpers. ``booleans``, ``bytes``, ``chars``,
  ``shorts``, ``ints``, ``longs``, ``floats``, and ``doubles`` now behave as
  Clojure-style casts over Basilisp's primitive-array representations instead of
  dummy identity functions. The shared primitive-array conformance fixture now
  covers successful casts and wrong-type rejection against Clojure.
* **Completed locally:** close the next core semantic tranche for bit operations
  and primitive-array access helpers. ``bit-shift-left``, ``bit-shift-right``,
  and ``unsigned-bit-shift-right`` now use Clojure/JVM signed 64-bit shift
  semantics, including masked shift counts and overflow behavior, instead of
  Python's unbounded shift contract. Shared fixtures now stress direct bit
  operations, negative and out-of-range shift counts, deterministic seeded bit
  fuzzing, ``alength``, ``aget``, generic ``aset``, typed ``aset-*`` helpers,
  ``amap``, and ``areduce``.
* **Completed locally:** close the core runtime-boundary semantic tranche for
  dynamic Vars and process-bound helpers. Shared fixtures now cover
  ``*1``/``*2``/``*3``/``*e`` binding behavior, ``assert`` expansion behavior,
  ``alter-var-root``, ``alter-meta!``, ``bound-fn``, ``bound-fn*``, ``*err*``,
  ``*flush-on-newline*``, agent error inspection/clearing, and root
  ``add-tap``/``remove-tap``/``tap>`` delivery. The core semantic coverage
  scanner now also recognizes REPL history dynamic Vars as direct value
  references instead of falsely leaving them uncovered.
* **Completed locally:** close a broad pure-core collection/function-helper
  semantic tranche. Shared fixtures now directly cover predicates, atom
  compare-and-set, transient ``assoc!``, flushing, ``comparator``, ``complement``,
  ``constantly``, ``completing``, bounded/lazy sequence helpers, ``filterv``,
  ``frequencies``, ``as->``, ``cond->>``, and seeded generated collection cases.
  The tranche fixed two concrete gaps: ``flatten`` now treats nested ``nil`` as
  a Clojure leaf instead of dropping it through ``seqable?`` recursion, and
  ``array-map`` now preserves insertion-order sequence semantics with duplicate
  keys retaining their original slot while updating the value.
* **Completed locally:** close the core lifecycle/runtime helper tranche.
  Shared fixtures now directly cover namespace creation/aliasing/removal,
  ``all-ns``, ``find-var``, ``get-thread-bindings``, ``default-data-readers``
  portable keys, ``delay?``/``force``, completed future lifecycle helpers,
  agent ``error-mode``/``error-handler`` behavior, and nil protocol extension
  lookup through ``extenders``, ``extends?``, ``find-protocol-impl``, and
  ``find-protocol-method``. The tranche fixed two concrete gaps: ``extends?``
  now accepts ``nil`` as a Clojure protocol extension target, and continue-mode
  agent failures clear handled errors and expose ``error-mode`` as a keyword.
* **Completed locally:** close the deterministic sequence/function/predicate
  helper tranche selected from the core semantic coverage audit. Shared
  fixtures now directly cover ``float?``, ``int?``, ``nat-int?``, ``neg-int?``,
  ``inst?``, ``map-entry?``, ``group-by``, ``interpose``, ``interleave``,
  ``line-seq``, ``iterator-seq``, ``every-pred``, ``memoize``, ``min-key``,
  ``max-key``, ``merge-with``, ``iteration``, and seeded generated collection
  combinations. The tranche fixed one concrete gap: ``min-key`` and
  ``max-key`` now reject the missing-value arity like Clojure instead of
  returning ``nil``. Direct ``clojure.core`` semantic fixture coverage is now
  ``443/679`` shared Vars, or ``65.2%``, with no missing Basilisp core publics.
* **Completed locally:** close the scalar numeric/parser helper tranche from
  the core semantic coverage audit. Shared fixtures now directly cover ``/``,
  ``+'``, ``-'``, ``min``, ``max``, ``num``, ``biginteger``, ``numerator``,
  ``denominator``, ``rationalize``, ``parse-boolean``, ``parse-double``,
  ``parse-long``, ``parse-uuid``, every public ``unchecked-*-int`` arithmetic
  helper, the corresponding signed 64-bit unchecked helpers, and seeded scalar
  helper fuzz cases. The tranche fixed Clojure-compatible exact
  ``rationalize`` for floating values, ratio-only ``numerator``/``denominator``
  accessors, signed 64-bit ``parse-long`` syntax and overflow boundaries,
  Java-compatible ``parse-uuid`` hyphenated group parsing, underscore rejection
  for ``parse-double``, and unchecked arithmetic wrapping/truncation. The core
  semantic coverage scanner now also treats the division symbol ``/`` as an
  unqualified call instead of mistaking it for a namespaced symbol. Direct
  ``clojure.core`` semantic fixture coverage is now ``473/679`` shared Vars, or
  ``69.7%``, with no missing Basilisp core publics.
* **Completed locally:** close the deterministic sequence
  segmentation/reduction helper tranche from the core semantic coverage audit.
  Shared fixtures now directly cover ``identity``, ``partial``, ``some-fn``,
  ``not-any?``, ``not-every?``, ``take-while``, ``take-nth``, ``take-last``,
  ``split-at``, ``splitv-at``, ``split-with``, ``partition-by``,
  ``partitionv``, ``partitionv-all``, ``reductions``, ``repeat``,
  ``replicate``, ``repeatedly``, ``replace``, and ``run!``, including seeded
  collection helper fuzz cases. The tranche fixed one concrete gap:
  ``replace`` now treats present map entries with ``nil`` or ``false`` values
  as replacements in collection and transducer arities instead of falling back
  to the original input. Direct ``clojure.core`` semantic fixture coverage is
  now ``492/679`` shared Vars, or ``72.5%``, with no missing Basilisp core
  publics.
* **Completed locally:** close the deterministic collection/reference/navigation
  helper tranche from the core semantic coverage audit. Shared fixtures now
  directly cover nested sequence navigation helpers, ``nthrest``/``nthnext``,
  ``list*``/``list?``, counted/indexed/reversible/sequential capability
  predicates, identifier predicates, positive/rational numeric predicates,
  ``reduce-kv``, ``update-keys``, ``update-vals``, ``vary-meta``, volatiles,
  atom value-return helpers, validators, watch removal, and
  ``if-let``/``if-some``/``when-let``/``when-some``/``when-first`` binding
  macros, including seeded collection fuzz cases. The tranche fixed six
  concrete Clojure gaps: ``reset-vals!`` and ``swap-vals!`` now return
  ``[old new]``; ``with-meta``/``vary-meta`` can clear metadata with ``nil``;
  ``when-first`` keys off collection emptiness instead of first-value
  truthiness; ``counted?`` recognizes persistent lists; ``list*`` returns the
  same cons/seq shape as Clojure for spliced arguments; and ``nthrest`` past the
  end returns an empty seq rather than ``nil``. Direct ``clojure.core``
  semantic fixture coverage is now ``531/679`` shared Vars, or ``78.2%``, with
  no missing Basilisp core publics.
* **Completed locally:** close the portable text, regex, and standard-input
  helper tranche from the core semantic coverage audit. A new shared fixture
  now directly covers ``format``, ``printf``, ``newline``, ``print-str``,
  ``println-str``, ``prn-str``, ``with-in-str``, ``read-line``,
  ``re-pattern``, ``re-matcher``, ``re-groups``, and ``re-seq`` across
  platform-normalized newline capture, human-readable vs reader-readable
  printing, stateful matcher groups, unmatched regex sequences, and seeded text
  fuzz cases. The tranche fixed one concrete Clojure gap: ``read-line`` now
  preserves non-newline trailing whitespace and returns ``nil`` at EOF while
  stripping only line terminators. Direct ``clojure.core`` semantic fixture
  coverage is now ``543/679`` shared Vars, or ``80.0%``, with no missing
  Basilisp core publics.
* **Completed locally:** close the portable hierarchy and multimethod helper
  tranche from the core semantic coverage audit. A new shared fixture now
  directly covers ``make-hierarchy``, ``descendants``, ``bases``, ``supers``,
  ``underive``, ``methods``, ``get-method``, ``prefers``, ``prefer-method``,
  ``remove-method``, and ``remove-all-methods`` across transitive derivation,
  underive recomputation, vector ``isa?`` dispatch, invalid hierarchy inputs,
  host class ancestry shape checks, ambiguous multimethod dispatch,
  preference-driven dispatch, default fallback, method removal, and seeded
  hierarchy fuzz cases. The tranche fixed one concrete Clojure gap:
  ``remove-all-methods`` now also clears multimethod preferences instead of
  leaving stale preference state behind. Direct ``clojure.core`` semantic
  fixture coverage is now ``553/679`` shared Vars, or ``81.4%``, with no
  missing Basilisp core publics.
* **Completed locally:** harden hierarchy/type behavior exposed by the
  ``algo-generic`` acceptance tranche. ``type`` now follows Clojure's
  ``nil`` boundary by returning ``nil`` for ``nil`` instead of Python
  ``NoneType``. Class ancestry now includes explicit hierarchy ancestors
  attached to superclasses, so deriving ``Object``/``python.object`` to a
  root keyword also makes subclasses satisfy that root in ``isa?`` and
  ``ancestors``. Variadic ``recur`` now rebinds the rest local to the final
  ``recur`` expression itself, including ``nil`` and non-seq values, matching
  Clojure's variadic arity boundary instead of repacking the value through
  Python ``*args``. Multimethod calls now support zero arguments when the
  dispatch function and selected method do, and ``defmulti`` Vars are marked
  redefable so method bodies do not direct-link a stale multifn value. The
  shared hierarchy/multimethod fixture now locks these behaviors against JVM
  Clojure.
* **Completed locally:** close the deterministic sequence/control/transducer
  helper tranche from the core semantic coverage audit. A new shared fixture
  now directly covers ``while``, ``lazy-cat``, ``trampoline``, ``tree-seq``,
  ``subseq``, ``rsubseq``, ``eduction``, and ``cat`` across loop return values,
  lazy realization order, trampolined recursion, depth-first traversal, sorted
  collection bounds, re-iterable eduction behavior, direct ``cat`` reducing
  function arities, transducer flattening, and seeded sequence fuzz cases. No
  implementation mismatch was found in this tranche; the fixture deliberately
  uses sorted maps for map-based tree traversal to avoid relying on unspecified
  ordinary map value order. Direct ``clojure.core`` semantic fixture coverage is
  now ``561/679`` shared Vars, or ``82.6%``, with no missing Basilisp core
  publics.
  The adversarial follow-up extends this fixture through stateful
  ``map-indexed``/``keep-indexed`` composition, partition completion,
  deterministic transducer-law rows across ``sequence``/``into``/``transduce``,
  and Clojure's custom ``halt-when`` completion-before-``retf`` ordering.
* **Completed locally:** close the portable Var/thread-binding/redefinition
  helper tranche from the core semantic coverage audit. A new shared fixture
  now directly covers ``var-get``, ``var-set``, ``thread-bound?``,
  ``get-thread-bindings``, ``push-thread-bindings``, ``pop-thread-bindings``,
  ``with-bindings*``, ``with-redefs``, and ``with-redefs-fn`` across root vs
  thread-local Var reads, thread-local mutation, dynamic binding frames,
  balanced low-level push/pop restoration, non-dynamic binding rejection,
  root redefinition restoration, exception restoration, degenerate
  ``with-redefs`` binding vectors, and seeded dynamic Var mutation fuzz cases.
  The tranche fixed one concrete Clojure gap: ``with-redefs`` now accepts empty
  and odd-length binding vectors like Clojure, where bindings are consumed via
  pair partitioning and any unpaired tail is ignored. The portable fixture
  intentionally avoids unmatched ``pop-thread-bindings`` because Clojure can
  corrupt its own process teardown frame after such a call. Direct
  ``clojure.core`` semantic fixture coverage is now ``569/679`` shared Vars, or
  ``83.8%``, with no missing Basilisp core publics.
* **Completed locally:** close the portable namespace state and resolution
  helper tranche from the core semantic coverage audit. A new shared fixture
  now directly covers ``all-ns``, ``find-ns``, ``the-ns``, ``create-ns``,
  ``remove-ns``, ``intern``, ``ns-aliases``, ``ns-imports``, ``ns-interns``,
  ``ns-map``, ``ns-publics``, ``ns-refers``, ``ns-resolve``, ``ns-unmap``,
  ``refer``, ``refer-clojure``, ``in-ns``, ``requiring-resolve``,
  ``loaded-libs``, ``alter-meta!``, and ``bound?`` across lifecycle lookup,
  missing namespace failure, public/private intern filtering, import-map shape,
  alias Namespace values, referred Var maps, renamed refers, current namespace
  switching/restoration, dynamic require resolution, loaded-library bookkeeping,
  and a seeded intern/private/unmap fuzz corpus. The tranche fixed two concrete
  Clojure gaps: ``the-ns`` now throws for missing namespace symbols instead of
  returning ``nil``, and ``ns-aliases`` now returns Namespace values rather than
  namespace-name symbols. Direct ``clojure.core`` semantic fixture coverage is
  now ``581/679`` shared Vars, or ``85.6%``, with no missing Basilisp core
  publics.
* **Completed locally:** close the portable collection/array/transient residual
  helper tranche from the core semantic coverage audit. A new shared fixture
  now directly covers ``disj``, ``rseq``, ``xml-seq``, ``to-array``,
  ``to-array-2d``, ``vector-of``, ``conj!``, ``disj!``, ``dissoc!``, and
  ``pop!`` across nil and sorted collection removal, reversible vectors and
  sorted maps, host-normalized XML depth-first traversal, nil/ragged array
  conversion, primitive vector coercion and rejection boundaries, transient
  map/set/vector mutation, ``conj!`` arity rejection, empty-vector pop errors,
  and a seeded transient/array fuzz corpus. The tranche fixed three concrete
  Clojure gaps: ``to-array`` now returns an empty array for ``nil``,
  ``to-array-2d`` now treats nil inner rows as empty rows, and ``conj!`` now
  follows Clojure's public arity boundary instead of accepting multiple new
  elements in one call. ``vector-of :boolean`` now also uses Clojure truthiness
  coercion. Direct ``clojure.core`` semantic fixture coverage is now
  ``591/679`` shared Vars, or ``87.0%``, with no missing Basilisp core publics.
* **Completed locally:** close the portable reader/eval/load boundary tranche
  from the core semantic coverage audit. A new shared fixture now directly
  covers ``read``, ``read+string``, ``reader-conditional``,
  ``reader-conditional?``, ``tagged-literal``, ``tagged-literal?``, ``eval``,
  ``load-reader``, ``load-string``, ``load-file``, ``load``, ``reset-meta!``,
  and ``test`` across EOF return values, source-preserving reads, default
  reader-conditional rejection, explicit reader-conditional allow/preserve
  modes, tagged literal construction and inspection, metadata reset, metadata
  backed test hooks, namespace-bound eval, reader/file/string loading, missing
  load resource rejection, and a seeded read/eval/read+string fuzz corpus. The
  tranche fixed concrete Clojure gaps in the public reader helpers:
  ``read-string`` and ``read`` now reject reader conditionals by default,
  ``read`` returns the supplied EOF value when EOF errors are disabled,
  ``read+string`` returns ``[eof ""]`` for an explicit EOF option, and public
  ``load-reader``/``load-string`` use Clojure's default reader-conditional
  rejection while ``load-file`` retains an internal permissive path for Basilisp
  source loading. A follow-up guard now also proves ``load-reader`` and
  ``load-string`` honor an internal ``ns`` form for subsequent loaded forms
  while restoring the caller's original ``*ns*`` after loading, matching
  Clojure's REPL/load boundary. Direct ``clojure.core`` semantic fixture
  coverage is now ``602/679`` shared Vars, or ``88.7%``, with no missing
  Basilisp core publics.
* **Completed locally:** close the portable definition-form and utility
  residual tranche from the core semantic coverage audit. A new shared fixture
  now directly covers ``declare``, ``defn-``, ``defstruct``, ``letfn``,
  ``destructure``, ``memfn``, ``memoize``, ``gensym``, ``time``, ``locking``,
  ``io!``, ``hash-combine``, ``mix-collection-hash``, ``hash-ordered-coll``,
  ``hash-unordered-coll``, ``class``, ``type``, ``cast``, ``find-keyword``,
  ``char-escape-string``, ``char-name-string``, ``record?``, ``uri?``,
  ``inst-ms*``, and ``unchecked-double`` across private definition metadata,
  declared Var binding state, struct construction, mutually recursive local
  functions, public destructuring expansion/evaluation, host-normalized method
  functions, memoization cache boundaries, gensym shape, timing output,
  locking, STM I/O guard boundaries, deterministic collection hash helpers,
  host-normalized type/class/cast behavior, interned keyword lookup, character
  escape/name maps, record/URI predicates, instants, and unchecked double
  coercion. The tranche fixed two concrete Clojure gaps: public ``destructure``
  now accepts a full binding vector and returns a vector suitable for ``let*``
  expansion, while internal macros use a private pair helper; ``cast`` now
  returns ``nil`` when asked to cast ``nil`` instead of throwing. Direct
  ``clojure.core`` semantic fixture coverage is now ``624/679`` shared Vars, or
  ``91.9%``, with no missing Basilisp core publics.
* **Completed locally:** close the portable concurrency, agent, and random
  residual tranche from the core semantic coverage audit. A new shared fixture
  now directly covers ``pmap``, ``pcalls``, ``pvalues``, ``rand``,
  ``rand-int``, ``rand-nth``, ``random-sample``, ``random-uuid``, ``shuffle``,
  ``send-off``, ``send-via``, ``restart-agent``, ``set-error-mode!``,
  ``set-error-handler!``, ``set-agent-send-executor!``, and
  ``set-agent-send-off-executor!`` across ordered parallel results,
  multi-collection parallel mapping, no-arg parallel calls, seeded parallel
  stress, random range/membership/permutation/UUID invariants, deterministic
  sample probabilities, send-off/send-via state transitions, failed-agent
  restart behavior, continue-mode error handlers, and fixture-owned executor
  replacement/cleanup. The tranche fixed a concrete Clojure gap:
  ``restart-agent`` now returns the supplied restart state for Clojure-compatible
  arities instead of returning the Agent object. Direct ``clojure.core``
  semantic fixture coverage is now ``640/679`` shared Vars, or ``94.3%``, with
  no missing Basilisp core publics.
* **Completed locally:** close the portable host/resource/printing utility
  tranche from the core semantic coverage audit. A new shared fixture now
  directly covers ``bean``, ``enumeration-seq``, ``add-classpath``,
  ``file-seq``, ``print-method``, ``print-dup``, ``munge``,
  ``namespace-munge``, ``use``, and ``compile`` across host-normalized bean
  properties, enumeration exhaustion, deprecated classpath mutation boundaries,
  root-inclusive recursive temp-tree traversal, seeded temp-tree traversal
  fuzzing, direct print multimethod dispatch, ``*print-dup*`` integration,
  runtime-specific munging invariants, ``use`` with ``:only``/``:rename``, and
  missing-namespace compile rejection. The tranche fixed a concrete Clojure
  gap: ``file-seq`` now includes the root path and correctly sequences
  ``pathlib.Path.rglob``'s single-use iterator instead of throwing. Direct
  ``clojure.core`` semantic fixture coverage is now ``650/679`` shared Vars, or
  ``95.7%``, with no missing Basilisp core publics.
* **Completed locally:** close the portable runtime dynamic Var and internal
  representation constructor tranche from the core semantic coverage audit. A
  new shared fixture now directly covers ``*'``, ``*command-line-args*``,
  ``*compiler-options*``, ``*reader-resolver*``, ``->ArrayChunk``,
  ``->Eduction``, ``->Vec``, ``->VecNode``, ``->VecSeq``, and
  ``StackTraceElement->vec`` across promoting multiplication identities,
  command-line argument shape, compiler option binding, reader resolver
  binding, host-normalized stack-trace tuple/vector conversion, eduction
  constructor iteration and seeded transducer stress, array chunk constructor
  boundaries, and vector/node/sequence constructor contracts. The fixture also
  exercises ``Inst`` and ``EMPTY-NODE`` directly; the direct coverage scanner
  now recognizes those intentional value references. Direct ``clojure.core``
  semantic fixture coverage is now ``660/679`` shared Vars, or ``97.2%``, with
  no missing Basilisp core publics.
* **Completed locally:** close the portable stream helper tranche from the core
  semantic coverage audit. A new shared fixture now directly covers
  ``stream-seq!``, ``stream-reduce!``, ``stream-transduce!``, and
  ``stream-into!`` across empty/non-empty terminal operations, no-init and
  explicit-init reductions, transducer completion, target metadata preservation,
  sorted target preservation, one-shot iterator inputs, early-termination
  overconsumption boundaries, and a seeded generated corpus combining stream
  sequencing, reductions, transductions, and into operations. The focused
  Basilisp stream API property tests also exposed and fixed an adjacent
  ``resultset-seq`` edge case: valid zero-column DB-API cursors no longer call
  ``distinct?`` with zero arguments before constructing the empty row basis.
  Direct ``clojure.core`` semantic fixture coverage is now ``664/679`` shared
  Vars, or ``97.8%``, with no missing Basilisp core publics.
* **Completed locally:** close the host-normalized proxy/interface tranche from
  the core semantic coverage audit. A new shared fixture now directly covers
  ``definterface``, ``gen-interface``, ``extend-type``, ``method-sig``,
  ``get-proxy-class``, ``construct-proxy``, ``init-proxy``, ``proxy-mappings``,
  ``update-proxy``, and ``proxy-super`` across interface generation, protocol
  extension, reflection-shape inspection, proxy class caching/construction,
  proxy initialization, mapping lookup, mapping update/clear behavior, super
  calls, invalid mapping target rejection, and seeded repeated proxy update
  stress. Assertions normalize the unavoidable host split: Clojure creates JVM
  proxy/interface classes while Basilisp creates Python proxy/interface classes,
  and the two runtimes intentionally differ on arbitrary extra proxy mapping
  validation. The ``clojure.core-proxy`` source-resource omission hardening
  follow-up now also covers duplicate proxy method rejection, portable
  multi-arity proxy dispatch, and exact ``proxy-call-with-super`` restoration
  when the original mapping deliberately contains a nil method entry. Basilisp
  now restores proxy method maps through ``init-proxy`` in that helper, so a
  super call cannot collapse nil-valued entries through ``update-proxy``'s
  remove-on-nil semantics. Local stress tests repeat exact restoration across
  nil/function mappings, symbol/string method names, and exception paths.
  Direct ``clojure.core`` semantic fixture coverage is now ``674/679`` shared
  Vars, or ``99.3%``, with no missing Basilisp core publics.
* **Completed locally:** close the final portable ``clojure.core`` semantic
  fixture residuals from the core semantic coverage audit. A new shared fixture
  now directly covers ``resultset-seq``, ``unquote``, and
  ``unquote-splicing`` across host-normalized JDBC ``ResultSet``/Python DB-API
  cursor row projection, case-normalized column labels, duplicate-label
  rejection, seeded row corpora, direct syntax-marker symbol availability, and
  syntax-quote unquote/splicing expansion contracts. The coverage scanner now
  treats ``EMPTY-NODE``, ``Inst``, ``unquote``, and ``unquote-splicing`` as
  intentional value/syntax references when they appear in shared fixtures.
  Direct ``clojure.core`` semantic fixture coverage is now ``679/679`` shared
  Vars, or ``100.0%``, with no missing Basilisp core publics.
* **Completed locally:** promote the broad behavioral parity proofs into CI.
  The ``run-parity-proofs`` workflow installs Java, Clojure CLI, Python 3.14,
  and Tox, then runs the cache-disabled differential conformance corpus across
  thirty-two stable, fixture-isolated shards and the cache-disabled source-level
  library acceptance corpus across three stable shards. This keeps full behavior
  and upstream-port proof from remaining local-only evidence without weakening
  the one-fixture-per-process diagnostic boundary.
* **Completed locally:** deepen ``clojure.tools.namespace`` semantic coverage.
  Shared fixtures now directly exercise dependency graphs, parse/read options,
  file and archive discovery, source-tree scanning, tracker update/removal,
  reload state transitions, classpath discovery under an isolated runtime
  path/classloader, and the deprecated root facade. The follow-up now also
  covers the ``MapDependencyGraph`` generated record/class boundary directly,
  raising direct semantic fixture coverage for
  ``clojure.tools.namespace.dependency`` to 100.0%. The root facade now matches
  Clojure's older reader-conditional boundary while the focused ``find`` and
  ``parse`` namespaces retain explicit ``:clj``/``:cljs``/``:lpy`` platform
  behavior. The graph/reload adversarial follow-up now differentially covers
  duplicate edges, deep and self-cycle rejection, remove-edge/remove-all/
  remove-node boundaries, missing-edge removal behavior, transitive dependency
  and dependent set queries, topo-order invariants, docstring/attr-map
  namespace declarations, ``:refer-clojure``/``:import``/``:gen-class``
  ignored clauses, prefix libspecs, ``:refer``/``:rename``/``:as-alias``
  options, host reader-conditionals, and invalid libspec rejection. A local
  deterministic tracker fuzz test now generates dependency chains and validates
  load/unload order plus graph-known removal behavior.
* **Completed locally:** add the remaining small ``clojure.tools.namespace``
  public subnamespaces ``clojure.tools.namespace.move`` and
  ``clojure.tools.namespace.repl`` to the standard surface matrix. ``move`` now
  exposes the upstream alpha destructive text-refactoring helpers
  ``replace-ns-symbol``, ``move-ns-file``, and ``move-ns`` over Python paths.
  ``repl`` is directly audited as a public namespace rather than only through
  root workflow behavior. Shared fixtures cover every public Var, scanner and
  empty-refresh return contracts, disable metadata, ``:after`` validation,
  textual namespace-token replacement, file moves, reference rewrites, and empty
  parent-directory pruning. Local tests add generated token-boundary replacement
  stress coverage and temp-tree move/prune checks.
* **Completed locally:** deepen ``clojure.spec.gen.alpha`` semantic coverage.
  Shared fixtures now directly exercise all primitive generators, generator
  combinators, lazy generator construction, named/predicate generator lookup,
  and ``quick-check``/``for-all*`` result contracts. This tranche raised direct
  semantic fixture coverage for ``spec.gen.alpha`` to 92.6% and fixed generated
  character representation, ``gen/not-empty`` collection filtering, and
  persistent-map item iteration for edge keys such as ``##NaN``. The follow-up
  now directly covers ``lazy-prim``, ``lazy-prims``, ``lazy-combinator``, and
  ``lazy-combinators``, raising direct semantic fixture coverage to 100.0% and
  fixing Basilisp lazy macro expansion so generated helper functions are
  callable like Clojure's implementation helpers. The adversarial follow-up now
  also locks ``s/gen`` named/path overrides, invalid override rejection,
  ``with-gen`` inside regex specs, and variable-length generation for ``s/*``
  and ``s/+``. Basilisp now wraps scalar ``with-gen`` values correctly in regex
  context and no longer collapses regex repeats to their minimum length.
* **Completed locally:** deepen ``clojure.math`` semantic coverage. Shared
  fixtures now directly exercise every public Var, including the previously
  uncovered ``expm1``, ``random``, and ``tanh`` edge behavior. Local regression
  tests stress small-value ``expm1`` stability, overflow-to-infinity behavior,
  ``tanh`` oddness and bounds, and repeated ``random`` sample bounds. This
  tranche raised direct semantic fixture coverage for ``clojure.math`` to
  100.0% without changing the advertised Python-hosted implementation boundary
  for fixed-width JVM integer overflow.
* **Completed locally:** deepen ``clojure.tools.reader`` root semantic
  coverage. Shared fixtures now directly exercise ``read``, ``read-string``,
  ``read+string``, ``read-regex``, ``read-symbol``, ``resolve-symbol``,
  dynamic data/default reader bindings, ``*suppress-read*``, ``*read-eval*``,
  reader-condition options, and source-logging EOF behavior. This tranche
  raised direct semantic fixture coverage for the root namespace to 100.0% and
  fixed the previously unbound ``read-symbol`` Var, ``*alias-map*`` resolution,
  Clojure-core symbol normalization, source metadata shape, and tools-reader
  ``#=`` read-eval enforcement. The adversarial follow-up now compares a
  deterministic corpus of scalar, collection, discard/comment, reader-constant,
  and reader-conditional forms, plus malformed input boundaries. It fixed the
  default reader-conditional mode so ``tools.reader`` rejects ``#?``/``#?@``
  unless callers explicitly request ``:read-cond :allow`` or
  ``:read-cond :preserve``, matching Clojure's source compatibility boundary.
  The source-boundary follow-up now differentially covers reader-conditional
  splicing inside vectors, lists, maps, discard forms, and nested reader
  conditionals, plus symbol/source-location normalization and ``read+string``
  form-boundary preservation across comments, discards, reader conditionals,
  and spliced map entries. Local deterministic fuzz tests now stress generated
  reader-conditional vector splicing and source-logging form boundaries so
  parser lookahead and source capture regressions fail close to the reader
  implementation. The EDN namespace follow-up adds
  ``clojure.tools.reader.edn`` with the upstream ``read``/``read-string``
  surface, restricted default readers for ``inst``/``uuid``, custom
  ``:readers``/``:default`` tag handling, and rejection coverage for non-EDN
  reader macros including syntax quote, unquote, deref, regex, var quote,
  anonymous functions, reader eval, reader conditionals, auto-resolved
  keywords, and Basilisp host tags. Leading apostrophes in EDN tokens and
  metadata remain accepted because upstream ``tools.reader.edn`` accepts them.
  The default-data-readers follow-up adds the upstream
  ``clojure.tools.reader.default-data-readers`` public surface, covering raw
  timestamp parsing, validation, Date/Calendar/Timestamp-style instant readers,
  UUID parsing, ``tools.reader`` custom data-reader integration, invalid input
  boundaries, and a seeded timestamp corpus. The ``impl.commons`` follow-up
  adds the upstream public helper surface for number regexes and
  ``match-number``, ``parse-symbol``, ``number-literal?``, ``read-past``,
  ``skip-line``, ``read-comment``, and ``throwing-reader``. Shared fixtures
  compare numeric radix/ratio/decimal boundaries, malformed numbers, symbol
  token edge cases, EOF-sensitive ``number-literal?`` nil behavior, and
  low-level pushback-reader line/comment skipping. The ``impl.utils`` follow-up
  adds the upstream character, whitespace, numeric, newline,
  metadata-desugaring, namespace-key, ``make-var``, ``ex-info?``, ``second'``,
  version-guard, and ``compile-when`` public helper surface, including direct
  macro coverage and a deterministic ASCII predicate corpus. The
  ``impl.inspect`` follow-up adds ``inspect`` and ``inspect*`` with scalar,
  string, collection, nested truncation, and boundary-corpus coverage; JVM
  internal seq class labels remain a host-specific rendering detail. The
  ``impl.errors`` follow-up adds the upstream reader error helper surface with
  exact ``ex-info`` message/data contracts for generic, EOF, reader-error,
  illegal-argument, metadata, namespace-map, reader-tag, Unicode/octal, and
  generated line/column location boundaries.
* **Completed locally:** deepen ``clojure.repl`` semantic coverage. Shared
  fixtures now directly exercise all audited REPL public Vars across portable
  search, ``dir``/``dir-fn``, documentation lookup, source lookup, demunging,
  root-cause traversal, bounded ``pst`` calls, stack-element formatting, and
  host-boundary helper availability. This tranche raised direct semantic
  fixture coverage for ``clojure.repl`` to 100.0% and fixed symbol-based
  ``source-fn``, missing-symbol ``source`` output, and Clojure-style
  ``demunge`` escape spellings.
* **Completed locally:** deepen ``clojure.core.server`` semantic coverage.
  Shared fixtures now directly exercise every audited public Var across pREPL
  entrypoint shape, ``*session*`` dynamic binding, ``repl-init``,
  ``repl-read``, absent server stops, no-op ``start-servers``, and invalid
  ``start-server`` rejection. This tranche raised direct semantic fixture
  coverage for ``clojure.core.server`` to 100.0% and fixed ``repl-read`` EOF
  handling so EOF returns the caller's exit sentinel while the literal ``nil``
  form remains a valid read result.
* **Completed locally:** deepen ``clojure.spec.test.alpha`` semantic coverage.
  Shared fixtures now directly exercise every audited public Var across symbol
  conversion, namespace enumeration, checkable/instrumentable discovery,
  instrumentation and ``with-instrument-disabled``, ``check`` target/option
  shapes, explicit ``check-fn`` fspec checking, and summary/abbreviation
  contracts. This tranche fixed empty discovery sets, Clojure-style
  test.check option maps, collection targets, Clojure-style successful summary
  counting/printing, explicit ``check-fn`` behavior, and generated checking for
  common portable predicate specs such as ``int?``/``integer?``.
* **Completed locally:** deepen ``clojure.test`` semantic coverage across every
  audited public Var. Shared fixtures now cover dynamic Vars, assertion-code
  helpers, fixture composition, report hooks/counters, ``try-expr``,
  metadata-backed tests, context strings, low-level runner return values,
  summary runners, and direct ``test-ns-hook`` calls. This tranche raised
  direct semantic fixture coverage for ``clojure.test`` to 100.0% and fixed
  Clojure-style thunk fixture composition, ``test-vars``/``test-all-vars``
  return values, direct ``deftest`` uncaught-error reporting, and
  ``testing-contexts-str``/``testing-vars-str`` formatting.

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
* source-level ``algo-generic`` acceptance added as the next real-library
  parity probe; it found and locked the ``type nil``, superclass-derived
  hierarchy, zero-arity multimethod invocation, ``defmulti`` direct-linking,
  and variadic ``recur`` rest-rebinding gaps above. Its n-ary comparison and
  arithmetic acceptance paths now run through upstream-style self-recursive
  multimethod methods instead of Basilisp-specific workarounds.
* source-level ``algo-monads`` acceptance added as a macro-heavy upstream port
  probe; it locks the public monad surface, ``domonad`` conditional expansion,
  ``defmonadfn`` symbol-macro helpers, sequence/maybe/set/writer/state/reader/
  continuation monads, transformer composition, and failure boundaries while
  reusing the accepted ``basilisp.tools.macro`` source substrate.
* source-level ``core-unify`` acceptance added as the next pure ``.cljc``
  upstream-library probe; it preserves the public symbolic unification API over
  Basilisp's ``zip`` and ``walk`` namespaces and locks wildcard/range variables,
  recursive binding flattening, substitution, factory-generated unifiers,
  no-occurs variants, occurs-check rejection, and explicit ordered map-pattern
  unification without importing JVM collection or test.check dependencies.
* source-level ``core-cache-memoize`` acceptance added as a stateful
  protocol-heavy upstream-library probe; it loads checked-in JVM snapshots of
  ``data.priority-map``, ``core.cache``, and ``core.memoize`` against Clojure
  while testing Basilisp's production namespaces through the standard
  ``clojure.core.cache`` and ``clojure.core.memoize`` aliases. It locks
  portable cache policy behavior, memoized-function snapshots and mutation
  helpers, cache/memoizer constructors, and protocol interop while keeping
  ``SoftReference`` support classified as JVM-only.
* source-level ``core.async`` acceptance added as an async real-library probe;
  it runs a multi-file portable workflow against ``org.clojure/core.async``
  1.9.865 and Basilisp's production facade. The probe covers coroutine-backed
  ``go``/``go-loop`` parking transforms, ``alt!`` priority/nested/put/timeout
  selection, ordered pipelines, collection/channel combinators, finite
  ``mult``/``pub`` routing, and a deterministic generated parking stress corpus.
  It also extends the acceptance harness so a library can declare extra Clojure
  Maven deps and request code-loaded entrypoint execution when direct script
  execution would leave runtime-owned async tasks alive.
* source-level ``data.csv`` acceptance added as a compact real-library probe;
  it runs a multi-file portable workflow against ``org.clojure/data.csv`` 1.1.0
  and Basilisp's production ``clojure.data.csv`` alias. The probe locks public
  surface, basic string/reader reads, writer output, ``read-csv-from`` integer
  delimiter entrypoints, custom separator/quote/newline behavior, scalar
  coercion, invalid-option parity, and deterministic generated round trips over
  comma, quote, CR, LF, CRLF, semicolon, and empty-field values.
* source-level ``core.match`` acceptance added as a macro-heavy real-library
  probe; it runs a multi-file portable workflow against
  ``org.clojure/core.match`` 1.1.1 and Basilisp's production
  ``clojure.core.match`` alias. The probe locks the Basilisp-native portable
  subset covering ``match``, ``matchm``, ``matchv``, ``match-let``, literals,
  wildcards, named bindings, vector/map/seq patterns, vector and seq rest
  patterns, application patterns, as-patterns, generated mixed-value
  classification, and no-match boundaries. The upstream snapshot remains too
  JVM/CLJS-compiler-specific to port wholesale, so extension namespaces such as
  ``array``, ``java``, and ``regex`` stay outside the claimed compatibility
  contract.
* source-level ``tools.namespace`` acceptance added as a host-adapted
  real-library probe; it runs a multi-file workflow against
  ``org.clojure/tools.namespace`` 1.5.0 and Basilisp's production
  ``clojure.tools.namespace`` aliases. The probe locks selected public
  facades, parser behavior for comments, docstrings, metadata, prefixed
  libspecs, aliases, ``:as-alias``, ``:use``, ``:require-macros``, and
  reader-conditionals, dependency graph updates, tracker load/unload ordering,
  48 deterministic generated acyclic graph cases, file/dir/JAR discovery, root
  facade behavior, namespace file moves, and token-boundary-aware namespace
  rewrites. The manifest remains host-adapted because the setup code must use
  JVM filesystem/JAR APIs on Clojure and Python filesystem/ZIP APIs on
  Basilisp, but the emitted acceptance contract is normalized data.
* ``Throwable->map`` diagnostics hardening now differentially locks thrown
  exception chains with ``:clojure.error/phase`` data, preserving Clojure's
  top-level ``:phase``, root-cause ``:cause``/``:data``, ordered ``:via``
  entries, per-entry ``:at`` vectors, and four-field ``:trace`` entries while
  allowing host-specific file/class names.
* Socket-backed nREPL diagnostics are now covered by the full contrib nREPL
  suite again. The bencode decoder now parses bencoded integer and byte-string
  lengths with Python's native integer parser instead of Clojure-compatible
  numeric coercion, restoring request decoding after stricter ``int`` parity.
  The related REPL/compiler follow-up keeps top-level form compilation aligned
  with the namespace currently selected by ``eval``/``ns`` forms, so multi-form
  CLI and REPL inputs can switch namespaces and continue evaluating like
  Clojure.
* Namespace bytecode cache hardening now treats corrupt or wrong-shaped
  marshaled ``.lpyc`` payloads as disposable cache misses after validating the
  source timestamp and size header. This preserves normal cached imports while
  recovering from interrupted writes or stale local cache artifacts by
  recompiling source and replacing the cache with a valid code-object payload.

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

Completed locally:

* ``py->lisp`` now accepts generic Python ``Mapping``, ``Sequence``, and
  ``Set`` implementations, while preserving strings, binary buffers, and
  existing Basilisp persistent collections as host/persistent values rather
  than over-converting them. This extends Python-native interop without adding
  a framework dependency or changing Clojure-facing semantics.

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
