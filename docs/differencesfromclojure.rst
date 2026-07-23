.. _differences_from_clojure:

Differences from Clojure
========================

Basilisp strives to be roughly compatible with Clojure, but just as ClojureScript `diverges from Clojure <https://clojurescript.org/about/differences>`_ at points, so too does Basilisp.
Being a hosted language like Clojure (which celebrates its host, rather than hiding it) means that certain host-specific constructs cannot be replicated on every platform.
We have tried to replicate the behavior of Clojure as closely as we can while still staying true to Python.

This document outlines the major differences between the two implementations so users of both can understand where Basilisp differs and adjust their code accordingly.
If a feature differs between the two implementations and it is not stated here, please first check if there is an open `issue on GitHub <https://github.com/basilisp-lang/basilisp/issues>`_ to implement or align the feature with Clojure or to clarify if it should be omitted.

.. _hosted_on_python:

Hosted on Python
----------------

Unlike Clojure, Basilisp is hosted on the Python VM.
Basilisp supports versions of Python 3.10+.
Basilisp projects and libraries may both import Python code and be imported by Python code (once the Basilisp runtime has been :ref:`initialized <bootstrapping>` and the import hooks have been installed).

``*basilisp-version*`` reports the installed Python-hosted runtime version.
For source compatibility, ``*clojure-version*`` and ``clojure-version`` report
the explicitly declared Clojure 1.12.4 target used by Basilisp's differential
corpus; they do not claim that the runtime itself is JVM Clojure.

.. _type_differences:

Type Differences
----------------

* ``nil`` corresponds to Python's ``None``\.
* Python does not offer different integer sizes, so ``short``, ``int``, and ``long`` are identical.
* Python does not offer different precision floating point numbers, so ``double`` and ``float`` are identical.
* Numeric values remain Python-hosted, but Clojure's scalar coercion functions
  enforce their accepted inputs and fixed-width bounds. ``float`` returns a
  Python float carrying JVM single-precision rounding; it cannot expose a
  distinct host float type.
* ``array-map``, sorted maps, and sorted sets are available. Their implementations
  use Python-hosted persistent collections rather than Clojure's JVM collection
  classes.

.. _arithmetic_comparison:

Arithmetic Comparison
---------------------

Basilisp keeps Clojure's integral, ratio, floating, and decimal equality
families distinct for ``=`` and for persistent map/set membership. ``==`` is
the cross-family numeric comparison. Python provides only one host
:external:py:class:`float` type, however, so Basilisp cannot retain Clojure's
additional distinction between a JVM single-precision ``float`` and a
double-precision value after either crosses the host boundary.

For values in the Basilisp language data model, ``hash`` uses Clojure's
deterministic signed 32-bit algorithms rather than Python's process-randomized
object hashes. Python-only objects still use a narrowed host hash because they
have no portable Clojure hash contract.

.. note::

   Basilisp's ``=`` will perform as expected when using Python :external:py:class:`decimal.Decimal` typed :ref:`floating-point numbers <numbers>`.

.. seealso::

   Python's `floating point arithmetic <https://docs.python.org/3/tutorial/floatingpoint.html>`_ documentation

.. _concurrent_programming:

Concurrent Programming
----------------------

Python is famous for it's `Global Interpreter Lock <https://docs.python.org/3/glossary.html#term-global-interpreter-lock>`_ limiting performance in the multi-core case.
As such, users may call into question the value of Clojure's concurrency-focused primitives in a single-threaded context.
However, ClojureScript's own `"Differences from Clojure" <https://clojurescript.org/about/differences>`_ document puts its best:

   Clojure’s model of values, state, identity, and time is valuable even in single-threaded environments.

That said, there are some fundamental differences and omissions in Basilisp that make it differ from Clojure.

* Atoms work just as in Clojure.
* ``basilisp.core`` provides synchronous ``Ref`` transactions through ``ref``,
  ``dosync``, ``alter``, ``ref-set``, ``commute``, and ``ensure``. History
  controls (``ref-history-count``, ``ref-min-history``, and
  ``ref-max-history``) retain the configured minimum committed values. ``io!``
  is available as an explicit side-effect guard, and agent dispatches are deferred until a
  successful transaction commit. Clojure's ``sync`` transaction syntax is also
  available; its flags argument is accepted and ignored as in Clojure.
* ``seque`` is available as a bounded queued lazy sequence. It uses a
  Python-owned daemon producer rather than Clojure's global Agent executor;
  consumer-visible values and completion behavior are preserved.
* Basilisp provides executor-backed Agents. ``await`` remains the Python async
  special form when unqualified, while ``clojure.core/await`` and
  ``basilisp.core/await`` expose the Clojure agent wait contract.
  ``await-agent`` remains the direct Python-oriented wait operation.
* All Vars are reified at runtime and users may use the :lpy:fn:`binding` macro as in Clojure.

  * Non-dynamic Vars are compiled into Python variables and references to those Vars are made using Python variables using :ref:`direct_linking`.
  * Vars are created in all cases, but only used in certain cases.

.. _reader_differences:

Reader
------

* :ref:`Numbers <reader_numeric_literals>`

  * Python integers natively support unlimited precision, so there is no difference between regular integers and those suffixed with ``N`` (which are read as ``BigInt``\s in Clojure).
  * Floating point numbers are read as Python ``float``\s by default and subject to the limitations of that type on the current Python VM.
    Floating point numbers suffixed with ``M`` are read as Python :external:py:class:`decimal.Decimal` types and support user-defined precision.
  * Ratios are supported and are read in as Python :external:py:class:`fractions.Fraction` types.
  * Python natively supports Complex numbers.
    The reader will return a complex number for any integer or floating point literal suffixed with ``J``.

* :ref:`Python data types <data_readers>`

  * The reader will return the native Python data type corresponding to the Clojure type in functionality if the value is prefixed with ``#py``.

.. _regular_expression_differences:

Regular Expressions
-------------------

Basilisp regular expressions use Python's :external:py:mod:`regular expression <re>` syntax and engine.

.. _repl_differences:

REPL
----

Basilisp's REPL experience closely matches that of Clojure's.

``basilisp.repl`` provides portable counterparts to Clojure's interactive
inspection helpers, including ``apropos``, ``dir``, ``dir-fn``, ``find-doc``,
``doc``, ``source``, ``source-fn``, ``root-cause``, and ``pst``. Python source
inspection can legitimately be unavailable for builtins and dynamically
created objects; ``source-fn`` returns ``nil`` in those cases. JVM-specific
``clojure.repl`` hooks for thread stopping, debugger break handlers, and Java
stack-frame rendering are intentionally omitted in favor of Python's native
debugger and traceback facilities.

.. _evaluation_differences:

Evaluation
----------

Basilisp code has the same evaluation semantics as Clojure.
The :lpy:fn:`load` and :lpy:fn:`load-file` functions are supported though their usage is generally discouraged.
Basilisp does not perform any locals clearing.

.. _special_form_differences:

Special Forms
-------------

Basilisp special forms should be identical to their Clojure counterparts unless otherwise noted below.

* :lpy:form:`def` does not support the ``^:const`` metadata key.
* :lpy:form:`if` does not use any boxing behavior as that is not relevant for Python.
* ``locking`` is available for Python context-manager locks. The JVM specific
  ``monitor-enter`` and ``monitor-exit`` special forms are not implemented.
* The Python VM specific :lpy:form:`await` and :lpy:form:`yield` forms are included to support Python interoperability.

.. _namespace_differences:

Namespaces
----------

Basilisp namespaces are reified at runtime and support the full set of ``clojure.core`` namespace APIs.
Namespaces correspond to a single Python `module <https://docs.python.org/3/library/sys.html#sys.modules>`_ which is where the compiled code (essentially anything that has been :lpy:form:`def`\-ed) lives.
Users should rarely need to be concerned with this implementation detail.

As in Clojure, namespaces are bootstrapped using the :lpy:fn:`ns` header macro at the top of a code file.
There are some differences between ``ns`` in Clojure and ``ns`` in Basilisp:

* Users may use ``:refer-basilisp`` and ``:refer-clojure`` interchangeably to control which of the :lpy:ns:`basilisp.core` functions are referred into the new namespace.
* Automatic namespace aliasing: if a namespaces starting with ``clojure.`` is required and does not exist, but a corresponding namespace starting with ``basilisp.`` does exist, Basilisp will import the latter automatically with the former as an alias.

.. _lib_differences:

Libs
----

Support for Clojure libs is `planned <https://github.com/basilisp-lang/basilisp/issues/668>`_\.

.. _xml_differences:

XML
---

``basilisp.xml`` supplies the portable data-oriented subset of ``clojure.xml``
and is available from the ``clojure.xml`` import path. ``parse`` returns immutable
``{:tag :attrs :content}`` maps, and ``emit``/``emit-element`` write that shape.
Unlike JVM Clojure's SAX-backed parser, it intentionally supports only
unqualified ASCII names. Namespace-qualified or non-ASCII names, DTDs, and
entity declarations are rejected; comments and processing instructions are not
retained. Input is text-only and bounded to 4 MiB by default (``:max-chars``).
This avoids silently changing namespace prefixes or opening XML entity-expansion
boundaries, but it is not a namespace-preserving or streaming XML API.

.. _core_lib_differences:

basilisp.core
-------------

- :lpy:fn:`basilisp.core/alter-var-root`: updates to a Var’s root via this function may not reflect in code that directly references the Var unless the Var is marked with ``^:redef`` metadata or declared as a dynamic variable. This is due to the :ref:`Direct Linking Optimization <direct_linking>` and differs with Clojure where such changes are always visible.

- Primitive array constructors (``boolean-array`` through ``double-array``) use
  mutable Python-hosted containers rather than JVM array classes. Their default
  values, fixed-width numeric coercion, and ``aget``/``aset`` (including the
  typed ``aset-*`` helpers) behavior are preserved. ``byte-array`` is a
  ``bytearray`` subclass: Lisp reads return signed byte values while Python
  binary APIs see its normal unsigned buffer.

.. _refs_and_transactions_differences:

Refs and Transactions
---------------------

``basilisp.core`` provides optimistic ``Ref`` transactions with versioned refs,
retrying ``dosync``, validators, watches, ``commute``, and ``ensure``. The
portable surface is checked by shared Clojure/Basilisp fixtures. Transaction
bodies must be synchronous and side-effect free because a conflict can cause
them to run more than once. ``ref-history-count``, ``ref-min-history``, and
``ref-max-history`` retain and report committed-history controls; Basilisp does
not use the JVM's adaptive snapshot queue. See :ref:`concurrency`.

.. _agents_differences:

Agents
------

Basilisp provides executor-backed agents with serialized actions, error handling,
and bounded waiting. Agent sends within a ``dosync`` transaction are deferred
until the transaction successfully commits. ``set-agent-send-executor!``,
``set-agent-send-off-executor!``, ``shutdown-agents``, and
``release-pending-sends`` are available with Clojure-shaped global behavior.
Python callers still own replacement and prior executor lifecycle. The one
syntax-level difference is that unqualified ``await`` remains async; use
``clojure.core/await`` or ``basilisp.core/await`` for an agent wait. See
:ref:`concurrency`.

.. _host_interop_differences:

Host Interop
------------

Host interoperability features generally match those of Clojure.

* :lpy:fn:`new` is a macro for Clojure compatibility, as the ``new`` keyword is not required for constructing new objects in Python.
* `Python builtins <https://docs.python.org/3/library/functions.html>`_ are available under the special namespace ``python`` (as ``python/abs``, for instance) without requiring an import.
* The qualified constructor form ``Classname/new`` introduced in Clojure 1.12 is not supported, because ``new`` is a valid Python method identifier unlike in Java.
* Qualified methods may be referenced with or without a leading ``.`` character regardless of whether they are static, class, or instance methods.
* ``PrintWriter-on`` returns a buffered callback-backed Python text writer. Its
  ``flush`` and ``close`` callbacks follow Clojure's lifecycle, while Python
  ``write``, ``print``, and ``println`` methods replace ``java.io.PrintWriter``.
* The deprecated ``add-classpath`` spelling accepts a local path or ``file:``
  URL, appends it to :external:py:data:`sys.path`, and invalidates Python import
  caches. It does not create or mutate a JVM class loader.
* ``stream-reduce!``, ``stream-seq!``, ``stream-transduce!``, and
  ``stream-into!`` accept Python iterables in place of Java streams. One-shot
  iterators retain terminal consumption semantics. ``resultset-seq`` accepts an
  executed Python DB-API cursor, using its ``description`` and ``fetchone``
  protocol in place of ``java.sql.ResultSet``.
* The three-argument ``ex-info`` form stores its explicit cause through
  Python's ``__cause__`` chain. ``ex-cause`` and ``Throwable->map`` preserve
  that chain, including unraised host exceptions that have no traceback frame.

.. seealso::

   :ref:`python_interop`

.. _type_hinting_differences:

Type Hinting
^^^^^^^^^^^^

Type hints may be applied anywhere they are supported in Clojure (as the ``:tag`` or ``:param-tags`` metadata keys), but the compiler does not currently use them for any purpose.
Tags provided for ``def`` names, function arguments and return values, and :lpy:form:`let` locals will be applied to the resulting Python AST by the compiler wherever possible.
Particularly in the case of function arguments and return values, these tags maybe introspected from the Python :external:py:mod:`inspect` module.
There is no need for type hints anywhere in Basilisp right now, however.
For explicit host-method reflection, ``method-sig`` returns a callable's
stable name, parameter annotations, and return annotation. Missing annotations
are ``nil``; these are Python annotations rather than Java ``Class`` objects,
and the callable is reflected without being invoked.

.. _compilation_differences:

Compilation
-----------

Basilisp's compilation is intended to work more like Clojure's than ClojureScript's, in the sense that code is meant to be JIT compiled from Lisp code into Python code at runtime.
Basilisp compiles namespaces into modules one form at a time, which brings along all of the attendant benefits (macros can be defined and immediately used) and drawbacks (being unable to optimize code across the entire namespace).
``gen-class`` is exposed as a source-compatible no-op macro. Basilisp does not
generate JVM ``.class`` files, but the public name and ``(:gen-class)`` namespace
clause are accepted so ordinary Clojure entrypoint namespaces can load.
:lpy:fn:`gen-interface` remains the Python-hosted interface-generation tool.
Users may still create dynamic classes using Python's ``type`` builtin, just as they could do in Python code.
Binding ``*warn-on-reflection*`` during compilation requests warnings for Python
host member lookup that must remain dynamic. It is a diagnostic only; unlike the
JVM switch it does not depend on Java type hints or change generated code.
Vectors use an immutable 32-way Python tree with 32-element tails, so ordinary
updates retain structural sharing across persistent values. The internal
``->Vec``, ``->VecNode``, ``->VecSeq``, and ``EMPTY-NODE`` names are available
for compatibility tooling; their ArrayManager position is accepted and ignored
because Python nodes use immutable tuples rather than JVM arrays.

.. seealso::

   :ref:`compiler`

.. _core_libraries_differences:

Core Libraries
--------------

Basilisp includes ports of some of the standard libraries from Clojure which should generally match the source in functionality.

* :lpy:ns:`basilisp.data` provides the portable ``clojure.data`` diffing
  surface, including ``Diff``, ``EqualityPartition``, ``diff``,
  ``diff-similar``, and ``equality-partition``. ``diff`` also accepts
  Python-native containers by converting them to Basilisp data before
  comparison.
* :lpy:ns:`basilisp.data.csv` provides the portable ``clojure.data.csv``
  reader/writer surface, including ``Read-CSV-From`` and ``read-csv-from``.
  It uses Python text streams rather than Java Reader/Writer values.
* :lpy:ns:`basilisp.data.json` provides the ``clojure.data.json`` read/write
  surface, including public default option maps, key/value transforms,
  extra-data hooks, and legacy names. It returns Basilisp persistent maps and
  vectors and supports ordinary Python text streams; non-seekable streams retain
  an internal unread suffix between calls instead of requiring a JVM
  ``PushbackReader``. Public pushback-reader constructor names are portable
  placeholders for source compatibility.
* :lpy:ns:`basilisp.data.xml` provides the namespace-aware XML tree, QName,
  PRXML, string/writer emit, lazy SAX ``event-seq``, and the two-way
  event/tree transforms from ``clojure.data.xml`` and
  ``clojure.data.xml.tree``. It rejects DTD/entity declarations. Event location
  metadata and lexical namespace-prefix maps are unavailable on Python's SAX
  API (``location-info`` is ``nil`` and ``nss`` is empty).
* :lpy:ns:`basilisp.data.codec.base64` provides the portable
  ``clojure.data.codec.base64`` byte-array API. It accepts Python bytes-like
  values and binary streams in place of JVM byte arrays and streams, while
  preserving data.codec's permissive table-based decode behavior for malformed
  input.
* :lpy:ns:`basilisp.data.priority-map` provides the persistent
  ``clojure.data.priority-map`` map/priority-queue contract. Its implementation
  orders entries on demand rather than exposing a JVM sorted-map representation.
  The public surface includes the upstream positional constructor and
  ``apply-keyfn`` macro for source compatibility; invalid hand-built internal
  field combinations are not a supported interchange format.
* :lpy:ns:`basilisp.datafy` is a port of ``clojure.datafy``
* :lpy:ns:`basilisp.core.rrb-vector` provides the public
  ``clojure.core.rrb-vector`` constructors, concatenation, and non-view
  slicing operations over ordinary persistent Basilisp vectors. It does not
  claim the JVM's specialized RRB storage or primitive unboxing layout.
* :lpy:ns:`basilisp.core.cache` and :lpy:ns:`basilisp.core.memoize` provide the
  portable persistent cache and memoization policies from ``core.cache`` and
  ``core.memoize``. Their generated constructor names are available for source
  compatibility. ``SoftCache`` and its reference-queue helpers resolve but
  raise explicitly because Python has no JVM ``SoftReference`` retention model.
* :lpy:ns:`basilisp.core.reducers` is the standard
  ``clojure.core.reducers`` import path for Basilisp's serial reducers port.
  ForkJoin-specific ``pool`` and ``fjtask`` resolve but raise when used.
* :lpy:ns:`basilisp.core.server` provides named socket-server lifecycle and
  ``repl``/``io-prepl``/``remote-prepl`` support through the
  ``clojure.core.server`` import path. Its generic listener uses Python text
  streams and a process-local registry. ``repl-read`` retains Clojure's quit
  behavior but cannot expose the JVM reader's line-start prompt sentinel.
* :lpy:ns:`basilisp.edn` is a port of ``clojure.edn``
* :lpy:ns:`basilisp.instant` provides the portable timestamp parser from
  ``clojure.instant`` and returns Python :external:py:class:`datetime.datetime`
  values rather than Java date, calendar, or timestamp classes. The ``#inst``
  reader accepts Clojure's partial timestamp grammar and normalizes offsets to
  UTC, but rejects leap seconds because Python has no native leap-second
  datetime value.
* :lpy:ns:`basilisp.io` is a port of ``clojure.java.io`` and is available
  through that standard import path. Its ``file`` and ``as-file`` entry points
  map to Python :class:`pathlib.Path` values, ``as-relative-path`` rejects
  absolute paths, ``as-url`` returns a parsed URL, and ``resource`` searches
  Python's import path for file resources rather than using a JVM class loader.
  Python-only helpers such as ``path``, ``exists?``, and ``touch`` remain on
  :lpy:ns:`basilisp.io` rather than the ``clojure.java.io`` alias.
* :lpy:ns:`basilisp.java.process` provides the ``clojure.java.process``
  import path over Python :external:py:class:`subprocess.Popen` objects. Its
  text-mode pipes follow Python newline normalization and ``io-task`` uses the
  Basilisp Future executor rather than JVM daemon threads.
* :lpy:ns:`basilisp.math` is a port of ``clojure.math``. Python's arbitrary-
  precision integers mean its ``*-exact`` functions do not overflow, and its
  ``round`` function does not have JVM ``long`` saturation behavior. Ordinary
  floating-point domains, signed zeros, exponent helpers, and next-value helpers
  are covered by shared Clojure/Basilisp fixtures.
* :lpy:ns:`basilisp.math.combinatorics` ports the dependency-free public
  ``clojure.math.combinatorics`` API through the standard import path. Its
  lazy sequence, multiset, direct-count, direct-index, and partition contracts
  are covered by a shared Clojure/Basilisp acceptance fixture.
* ``medley.core`` is available as a portable upstream-library port. Its public
  functional collection operations use Basilisp collections and Python UUID and
  regular-expression values instead of JVM implementation classes.
* :lpy:ns:`basilisp.pprint` is a port of ``clojure.pprint``, including
  ``cl-format`` and Basilisp's first-class character values.
* :lpy:ns:`basilisp.reducers` provides the serial reducible and foldable subset
  of ``clojure.core.reducers``. It preserves Clojure's map-reduction arity
  boundary, but it does not create a global parallel worker pool.
* :lpy:ns:`basilisp.set` is a port of ``clojure.set``
* :lpy:ns:`basilisp.shell` is a port of ``clojure.java.shell`` and is
  available through that standard import path. Its public alias surface,
  result maps, stdin, environment and directory bindings, byte output, and
  repeated command behavior are covered by shared Clojure/Basilisp fixtures.
* :lpy:ns:`basilisp.spec.alpha` provides portable validation, conforming,
  first-class ``spec``/``conformer``/``nonconforming`` descriptors, map
  merging, ``every``/``every-kv``, sequence specs, and ``fspec``/``fdef``
  descriptors. ``int-in``, ``double-in``, ``inst-in``, and runtime-toggleable
  ``s/assert`` checks use Python integer, float, and ``datetime`` values. The
  public ``clojure.spec.alpha`` surface is available, including the documented
  dynamic Vars, protocol/helper names, implementation-constructor helpers, and
  registry/explain printer entrypoints; those helpers delegate to Basilisp's
  portable descriptor engine rather than JVM spec internals. ``s/keys`` supports
  Clojure's qualified and unqualified key modes (``:req``, ``:opt``,
  ``:req-un``, and ``:opt-un``), and ``s/keys*`` validates alternating
  keyword/value regex sequences before conforming them to maps. Its opt-in
  :lpy:ns:`basilisp.spec.test.alpha` public surface now matches
  ``clojure.spec.test.alpha``. Instrumentation validates calls through Basilisp
  Vars only and offers Hypothesis-backed checking for known portable descriptor
  domains or explicit ``with-gen`` strategies.
  :lpy:ns:`basilisp.spec.gen.alpha` provides the standard
  ``clojure.spec.gen.alpha`` generator facade, including Clojure-style
  primitive constructors and built-in predicate generators. ``s/gen``,
  ``s/exercise``, and ``s/exercise-fn`` generate portable predicate,
  collection, map, key, tuple, regex, and explicit ``with-gen`` descriptors.
  Recursive, ``multi-spec``, and function-value generation still require an
  explicit ``with-gen`` strategy.
* :lpy:ns:`basilisp.stacktrace` is a port of ``clojure.stacktrace``. It exposes
  the standard public stacktrace helpers while formatting Python traceback
  frames rather than JVM ``StackTraceElement`` values.
* :lpy:ns:`basilisp.string` is a port of ``clojure.string``. It also includes
  Python-native helpers such as ``lpad``/``rpad`` and the historical
  ``trim-newlines`` spelling; ``trim-newline`` is the standard Clojure spelling.
* :lpy:ns:`basilisp.test` is a port of ``clojure.test``. It supports the
  standard low-level ``test-var``/``:test`` metadata path, report counters,
  output rebinding, and assertion-extension helpers alongside Basilisp's
  PyTest-oriented structured test results. Stack locations use Python frames,
  and ordinary Python text writers replace JVM ``PrintWriter`` values.
* :lpy:ns:`basilisp.test.check` supplies the portable ``clojure.test.check``
  property-testing boundary: deterministic seeded generation, composable
  generators, shrinking, ``for-all``, ``quick-check``, and ``defspec``. Its
  random implementation is Python-hosted, so a seed is reproducible within
  Basilisp but does not promise Java ``SplittableRandom`` byte-for-byte output.
* :lpy:ns:`basilisp.test.tap` is a port of ``clojure.test.tap`` for REPL test
  runners. ``clojure.test.junit`` remains JVM-specific and is not provided.
* :lpy:ns:`basilisp.tools.logging` provides the portable
  ``clojure.tools.logging`` macro API over Python's :external:py:mod:`logging`
  module. Its trace level maps to Basilisp's level 5 and fatal maps to Python
  ``CRITICAL``; logger back-end selection follows Python configuration rather
  than SLF4J/JUL discovery. The public ``impl`` protocol/factory surface is
  available, with Java backend selectors returning ``nil``. An upstream
  generated proxy-class Var may appear in JVM ``ns-publics`` and is intentionally
  not exposed.
* :lpy:ns:`basilisp.tools.reader` provides the portable
  ``clojure.tools.reader`` single-form reader and its stateful
  ``reader-types`` constructors. Its public surface now matches upstream
  ``tools.reader`` and ``reader-types`` for the portable names, including
  constructor/coercer helpers. It preserves stream lookahead across repeated
  reads, returns Basilisp ``Character`` values from ``read-char``/``peek-char``,
  and supports source logging, reader-condition options, and tagged reader
  bindings. JVM reader evaluation and Java class construction remain
  intentionally unavailable.
* :lpy:ns:`basilisp.tools.namespace` provides the portable source discovery,
  dependency tracking, and REPL refresh workflow from
  ``clojure.tools.namespace``. Its default refresh platform is Basilisp
  ``.lpy``/``.cljc`` source with the ``:lpy`` feature; ``:clj`` and ``:cljs``
  discovery platforms remain available explicitly. Deprecated root classpath
  helpers scan Python's ``sys.path`` instead of a JVM classpath. The upstream
  alpha, destructive source-moving API is intentionally omitted.
* :lpy:ns:`basilisp.walk` is a port of ``clojure.walk``
