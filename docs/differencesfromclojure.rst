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

.. _type_differences:

Type Differences
----------------

* ``nil`` corresponds to Python's ``None``\.
* Python does not offer different integer sizes, so ``short``, ``int``, and ``long`` are identical.
* Python does not offer different precision floating point numbers, so ``double`` and ``float`` are identical.
* Type coercions generally delegate to the relevant Python constructor, which handles such things natively.
* ``array-map``, sorted maps, and sorted sets are available. Their implementations
  use Python-hosted persistent collections rather than Clojure's JVM collection
  classes.

.. _arithmetic_comparison:

Arithmetic Comparison
---------------------

Basilisp, in contrast to Clojure, does not distinguish between integer (``int``) and floating point (``float``) as `separate categories for equality comparison purposes <https://clojure.org/guides/equality>`_ where the ``=`` comparison between any ``int`` and ``float`` returns ``false``.
Instead, it adopts Python's ``=`` comparison operator semantics, where the ``int`` is optimistically converted to a ``float`` before the comparison. However, beware that this conversion can lead to `certain caveats in comparison <https://stackoverflow.com/a/30100743>`_ where in rare cases seemingly exact ``int`` and ``float`` numbers may still compare to ``false`` due to limitations in floating point number representation.

In Clojure, this optimistic equality comparison is performed by the ``==`` function. In Basilisp, ``==`` is aliased to behave the same as ``=``.

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
  controls remain omitted because they expose JVM-specific retention policy
  rather than portable transactional semantics. ``io!`` is available as an
  explicit side-effect guard, and agent dispatches are deferred until a
  successful transaction commit. Clojure's ``sync`` transaction syntax is also
  available; its flags argument is accepted and ignored as in Clojure.
* ``seque`` is available as a bounded queued lazy sequence. It uses a
  Python-owned daemon producer rather than Clojure's global Agent executor;
  consumer-visible values and completion behavior are preserved.
* Basilisp provides executor-backed Agents.
  ``await-agent`` is the synchronous wait operation; ``await`` remains the
  Python async special form and is intentionally not repurposed as an agent
  wait function.
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
* Prefix lists are not supported for any of the import or require selectors.
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

- :lpy:fn:`basilisp.core/float` coerces its argument to a floating-point number. When given a string input, Basilisp will try to parse it as a floating-point number, whereas Clojure will raise an error if the input is a character or a string.

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
them to run more than once. JVM Ref history controls remain intentionally
omitted. See :ref:`concurrency`.

.. _agents_differences:

Agents
------

Basilisp provides executor-backed agents with serialized actions, error handling,
and bounded waiting. Agent sends within a ``dosync`` transaction are deferred
until the transaction successfully commits. Agents do not provide JVM executor
controls. In particular,
``set-agent-send-executor!``, ``set-agent-send-off-executor!``, and
``shutdown-agents`` are intentionally unavailable because Python executors have
explicit application ownership. See :ref:`concurrency`.

.. _host_interop_differences:

Host Interop
------------

Host interoperability features generally match those of Clojure.

* :lpy:fn:`new` is a macro for Clojure compatibility, as the ``new`` keyword is not required for constructing new objects in Python.
* `Python builtins <https://docs.python.org/3/library/functions.html>`_ are available under the special namespace ``python`` (as ``python/abs``, for instance) without requiring an import.
* The qualified constructor form ``Classname/new`` introduced in Clojure 1.12 is not supported, because ``new`` is a valid Python method identifier unlike in Java.
* Qualified methods may be referenced with or without a leading ``.`` character regardless of whether they are static, class, or instance methods.

.. seealso::

   :ref:`python_interop`

.. _type_hinting_differences:

Type Hinting
^^^^^^^^^^^^

Type hints may be applied anywhere they are supported in Clojure (as the ``:tag`` or ``:param-tags`` metadata keys), but the compiler does not currently use them for any purpose.
Tags provided for ``def`` names, function arguments and return values, and :lpy:form:`let` locals will be applied to the resulting Python AST by the compiler wherever possible.
Particularly in the case of function arguments and return values, these tags maybe introspected from the Python :external:py:mod:`inspect` module.
There is no need for type hints anywhere in Basilisp right now, however.

.. _compilation_differences:

Compilation
-----------

Basilisp's compilation is intended to work more like Clojure's than ClojureScript's, in the sense that code is meant to be JIT compiled from Lisp code into Python code at runtime.
Basilisp compiles namespaces into modules one form at a time, which brings along all of the attendant benefits (macros can be defined and immediately used) and drawbacks (being unable to optimize code across the entire namespace).
``gen-class`` is not required or implemented in Basilisp, but :lpy:fn:`gen-interface` is.
Users may still create dynamic classes using Python's ``type`` builtin, just as they could do in Python code.

.. seealso::

   :ref:`compiler`

.. _core_libraries_differences:

Core Libraries
--------------

Basilisp includes ports of some of the standard libraries from Clojure which should generally match the source in functionality.

* :lpy:ns:`basilisp.data` is a port of ``clojure.data``
* :lpy:ns:`basilisp.data.csv` provides the portable ``clojure.data.csv``
  reader/writer surface. It uses Python text streams rather than Java
  Reader/Writer values.
* :lpy:ns:`basilisp.data.json` provides the ``clojure.data.json`` read/write
  surface, including key/value transforms, extra-data hooks, and legacy names.
  It returns Basilisp persistent maps and vectors and supports ordinary Python
  text streams; non-seekable streams retain an internal unread suffix between
  calls instead of requiring a JVM ``PushbackReader``.
* :lpy:ns:`basilisp.data.codec.base64` provides the portable
  ``clojure.data.codec.base64`` byte-array API. It accepts Python bytes-like
  values and binary streams in place of JVM byte arrays and streams.
* :lpy:ns:`basilisp.data.priority-map` provides the persistent
  ``clojure.data.priority-map`` map/priority-queue contract. Its implementation
  orders entries on demand rather than exposing a JVM sorted-map representation.
* :lpy:ns:`basilisp.datafy` is a port of ``clojure.datafy``
* :lpy:ns:`basilisp.core.server` provides named socket-server lifecycle and
  ``repl``/``io-prepl``/``remote-prepl`` support through the
  ``clojure.core.server`` import path. Its generic listener uses Python text
  streams and a process-local registry. ``repl-read`` retains Clojure's quit
  behavior but cannot expose the JVM reader's line-start prompt sentinel.
* :lpy:ns:`basilisp.edn` is a port of ``clojure.edn``
* :lpy:ns:`basilisp.instant` provides the portable timestamp parser from
  ``clojure.instant`` and returns Python :external:py:class:`datetime.datetime`
  values rather than Java date, calendar, or timestamp classes.
* :lpy:ns:`basilisp.io` is a port of ``clojure.java.io`` and is available
  through that standard import path. Its ``file`` and ``as-file`` entry points
  map to Python :class:`pathlib.Path` values, ``as-relative-path`` rejects
  absolute paths, ``as-url`` returns a parsed URL, and ``resource`` searches
  Python's import path for file resources rather than using a JVM class loader.
* :lpy:ns:`basilisp.java.process` provides the ``clojure.java.process``
  import path over Python :external:py:class:`subprocess.Popen` objects. Its
  text-mode pipes follow Python newline normalization and ``io-task`` uses the
  Basilisp Future executor rather than JVM daemon threads.
* :lpy:ns:`basilisp.math` is a port of ``clojure.math``. Python's arbitrary-
  precision integers mean its ``*-exact`` functions do not overflow, and its
  ``round`` function does not have JVM ``long`` saturation behavior.
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
  of ``clojure.core.reducers``. It does not create a global parallel worker pool.
* :lpy:ns:`basilisp.set` is a port of ``clojure.set``
* :lpy:ns:`basilisp.shell` is a port of ``clojure.java.shell`` and is
  available through that standard import path.
* :lpy:ns:`basilisp.spec.alpha` provides portable validation, conforming,
  first-class ``spec``/``conformer``/``nonconforming`` descriptors, map
  merging, ``every``/``every-kv``, sequence specs, and ``fspec``/``fdef``
  descriptors. ``int-in``, ``double-in``, ``inst-in``, and runtime-toggleable
  ``s/assert`` checks use Python integer, float, and ``datetime`` values. Its opt-in
  :lpy:ns:`basilisp.spec.test.alpha` instrumentation validates calls through
  Basilisp Vars only and offers Hypothesis-backed checking for known portable
  descriptor domains or explicit ``with-gen`` strategies.
  :lpy:ns:`basilisp.spec.gen.alpha` provides the standard
  ``clojure.spec.gen.alpha`` generator facade, including Clojure-style
  primitive constructors and built-in predicate generators. ``s/gen``,
  ``s/exercise``, and ``s/exercise-fn`` generate portable predicate,
  collection, map, key, tuple, regex, and explicit ``with-gen`` descriptors.
  Recursive, ``multi-spec``, and function-value generation still require an
  explicit ``with-gen`` strategy.
* :lpy:ns:`basilisp.stacktrace` is a port of ``clojure.stacktrace``
* :lpy:ns:`basilisp.string` is a port of ``clojure.string``
* :lpy:ns:`basilisp.test` is a port of ``clojure.test``
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
  than SLF4J/JUL discovery.
* :lpy:ns:`basilisp.tools.reader` provides the portable
  ``clojure.tools.reader`` single-form reader and its stateful
  ``reader-types`` constructors. It preserves stream lookahead across repeated
  reads and supports source logging, reader-condition options, and tagged
  reader bindings. JVM reader evaluation and Java class construction remain
  intentionally unavailable.
* :lpy:ns:`basilisp.tools.namespace` provides the portable source discovery,
  dependency tracking, and REPL refresh workflow from
  ``clojure.tools.namespace``. Its default refresh platform is Basilisp
  ``.lpy``/``.cljc`` source with the ``:lpy`` feature; ``:clj`` and ``:cljs``
  discovery platforms remain available explicitly. The upstream alpha,
  destructive source-moving API is intentionally omitted.
* :lpy:ns:`basilisp.walk` is a port of ``clojure.walk``
