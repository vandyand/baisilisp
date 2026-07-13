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
  lazy-realization behavior, macro expansion, exception data, ``seque``,
  deterministic Agent/Ref transactions, and ``clojure.test`` assertion,
  reporting, custom-assertion, and fixture effects. New public compatibility
  names should arrive with a portable fixture or a documented host-specific
  reason why a shared fixture is impossible.

4. Standard Namespace Coverage
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Standard namespaces make Basilisp more useful before applications need custom
interop. They also reduce friction when porting small Clojure libraries.

Initial targets:

* pREPL server (`#628 <https://github.com/basilisp-lang/basilisp/issues/628>`_)
* ``pprint/code-dispatch`` (`#1266 <https://github.com/basilisp-lang/basilisp/issues/1266>`_)
* ``core.async`` or a Python-native async alternative (`#149 <https://github.com/basilisp-lang/basilisp/issues/149>`_)

Near-term deliverable:

* prioritize namespaces with small, testable API surfaces before larger
  runtime-level features

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
