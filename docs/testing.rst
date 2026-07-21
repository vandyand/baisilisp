.. _testing:

Testing
=======

.. lpy:currentns:: basilisp.test

Basilisp includes a `PyTest <https://docs.pytest.org/>`_ plugin which supports running tests defined using the functions and macros in :lpy:ns:`basilisp.test`.
PyTest can be installed alongside Basilisp by specifying the ``pytest`` extra when installing::

   pip install baisilisp[pytest]

Tests should be located in a ``tests/`` directory off of the project root, as outlined in :ref:`project_structure`.
Basilisp test files should end with an ``.lpy`` suffix and the file basename should either be prefixed with ``test_`` or suffixed with ``_test``.
Tests can be executed using the :ref:`CLI <run_basilisp_tests>` or can be run directly using PyTest's provided CLI.

.. note::

   Basilisp supports executing both Basilisp and Python tests in the same test suite, so long as the Python tests are written using PyTest.

Tests can be written by wrapping your logic and assertions in a :lpy:fn:`deftest` form.
Basic test assertions are written using the :lpy:fn:`is` macro.
Tests within a ``deftest`` can be wrapped in an :lpy:fn:`testing` macro to both document the test function and to provide more informative testing output when tests fail.
For asserting repeatedly against different inputs, you can use the :lpy:fn:`are` templating function.

.. code-block:: clojure

   (ns my-project.test-core
    (:require [basilisp.test :refer [deftest is are testing]]))

   (deftest my-test
     (is true)

     (testing "false is really false"
       (is (not false))))

   (deftest test-adding
     (are [res x y] (= res (+ x y))
       3  1 2
       4  2 2
       0 -1 1)

Property Tests
--------------

The portable ``clojure.test.check`` import path is also available. Use
``for-all`` to describe generated inputs and ``defspec`` to register the
property with the normal Basilisp/PyTest runner. A fixed ``:seed`` makes a
failing run reproducible.

.. code-block:: clojure

   (ns my-project.property-test
     (:require [clojure.test.check.generators :as gen]
               [clojure.test.check.properties :as prop]
               [clojure.test.check.clojure-test :refer [defspec]]))

   (defspec reversing-a-vector-twice 500
     (prop/for-all [xs (gen/vector gen/small-integer)]
       (= xs (vec (reverse (reverse xs))))))

For exploratory use, call ``clojure.test.check/quick-check`` directly. Its
result includes ``:seed``, and failures include ``:fail`` and ``:shrunk`` with
the smallest counterexample found.

Specs that need an explicit generator can use the standard
``clojure.spec.gen.alpha`` import path. Its primitive generators are
zero-argument constructors, matching Clojure's public API.

.. code-block:: clojure

   (require '[clojure.spec.gen.alpha :as sgen])

   (sgen/generate (sgen/vector (sgen/int) 1 4))

``clojure.spec.alpha/gen`` builds those generators from portable spec
descriptors. ``exercise`` returns generated values paired with their conformed
forms, and ``exercise-fn`` applies a function to samples from its ``fdef``
argument spec.

.. code-block:: clojure

   (require '[clojure.spec.alpha :as s]
            '[clojure.spec.gen.alpha :as sgen])

   (sgen/generate (s/gen (s/coll-of int? :min-count 1 :max-count 4)))

.. _testing_repl:

Running Tests at the REPL
-------------------------

The PyTest plugin remains the normal project test runner. For interactive work,
``basilisp.test`` also provides ``run-test``, ``run-test-var``, ``run-tests``, and
``run-all-tests``. They execute ``deftest`` Vars using the namespace's declared
fixtures, print a summary, and return a map with ``:test``, ``:pass``, ``:fail``,
and ``:error`` counts. ``successful?`` returns whether a summary has no failures
or errors. The standard ``clojure.test`` import path also supplies low-level
``test-var``, ``*report-counters*``, ``with-test-out``, and assertion extension
helpers, so Clojure-oriented custom reporters can run unchanged over ordinary
Python text writers.

.. code-block:: clojure

   (require '[basilisp.test :as test])

   ;; Run all tests in a loaded namespace.
   (test/run-tests 'my-project.core-test)

   ;; Run one known test Var.
   (test/run-test-var #'my-test)

   ;; Run one known test by name.
   (test/run-test my-test)

``test-ns`` respects an optional ``test-ns-hook`` in the target namespace. A hook
can directly call selected ``deftest`` functions; their results are combined into
the normal namespace summary.

TAP Output
----------

``basilisp.test.tap`` renders ``basilisp.test`` results as the Test Anything
Protocol (TAP). Wrap a REPL runner call in ``with-tap-output`` to emit ``ok`` or
``not ok`` assertion lines, diagnostics, and a final plan while suppressing the
normal human-oriented runner output.

.. code-block:: clojure

   (require '[basilisp.test :as test]
            '[basilisp.test.tap :as tap])

   (tap/with-tap-output
     (test/run-tests 'my-project.core-test))

The wrapped call still returns the ordinary test summary map. Fixture, uncaught
test, and ``test-ns-hook`` errors are reported as failing TAP events so the
plan remains accurate.

Custom Assertions and Definition Tests
--------------------------------------

``assert-expr`` is a public multimethod used by ``is``. Applications can add
methods for custom assertion forms; each method should return code that calls
``do-report`` with a ``:pass``, ``:fail``, or ``:error`` event.

``with-test`` and ``set-test`` attach assertions to existing Vars, while
``deftest-`` creates a private test Var. Bind ``*load-tests*`` to ``false``
while loading production code to omit all of these test definitions.

.. _testing_path:

Testing and ``PYTHONPATH``
--------------------------

Typical Clojure projects will have parallel ``src/`` and ``test/`` folders in the project root.
Project management tooling typically constructs the Java classpath to include both parallel trees for development and only ``src/`` for deployed software.
Basilisp uses Python packaging for dependencies and can declare source and test
import paths in ``pyproject.toml``:

.. code-block:: toml

   [tool.basilisp]
   source-paths = ["src"]
   test-paths = ["test"]

With this configuration, ``basilisp test`` discovers and imports test
namespaces from ``test`` without an additional ``--include-path`` flag.

The easiest solution to facilitate test discovery with Pytest (Basilisp's default test runner) is to create a ``tests`` directory:

.. code-block:: text

   tests
   └── myproject
       └── core_test.lpy

Test namespaces can then be created as if they are part of a giant ``tests`` package:

.. code-block:: clojure

   (ns tests.myproject.core-test)

Tests can be run with:

.. code-block:: shell

   $ basilisp test

----

Alternatively, you can follow the more traditional Clojure project structure by creating a ``test`` directory for your test namespaces:

.. code-block:: text

   test
   └── myproject
       └── core_test.lpy

In this case, the test namespace can start at ``myproject``:

.. code-block:: clojure

   (ns myproject.core-test)


Without project configuration, the ``test`` directory can be explicitly added
to the ``PYTHONPATH`` using the ``--include-path`` (or ``-p`` or the
``PYTHONPATH`` environment variable) option when running the tests:

.. code-block:: shell

   $ basilisp test --include-path test

.. note::

   Test directory names can be arbitrary.
   By default, the test runner searches all subdirectories for tests.
   In the first example above (``tests``, a Python convention), the top-level directory is already in the ``PYTHONPATH``, allowing ``tests.myproject.core-test`` to be resolvable.
   In the second example (``test``, a Clojure convention), the test directory is explicitly added to the ``PYTHONPATH``, enabling ``myproject.core-test`` to be resolvable.

.. warning::

   In versions of Basilisp prior to v0.5.1, you will also want to specify ``--include-unsafe-path=false`` to disable Python prepending the empty string ``""`` (meaning the current directory) to the path.
   Without this, PyTest will attempt to collect your namespace from ``./test`` first, which will attempt to import your test namespaces as ``test.{namespace}``, which will fail collection.

   After version v0.5.1, ``basilisp test`` automatically prepends ``tests`` and ``test`` (if either exist) to the ``PYTHONPATH``.
   You can disable this behavior by passing ``--include-default-test-path=false`` or ``-d false``.

.. _test_settings:

Test Settings
-------------

PyTest typically searches the entire root directory recursively for test based on its own heuristics.
For projects which don't follow those patterns, it may be necessary to configure the test discovery more precisely.

To configure Basilisp to search only specific directories for Basilisp test files, set the ``BASILISP_TEST_PATH`` variable.
Like other ``PATH``-like variables, you can specify multiple directories separated by your operating system's default path separator.
If this variable is not set, Basilisp tests will be discovered using PyTest's default discovery.

Within any eligible path, Basilisp will only load up files for tests matching the regular expression pattern given in ``BASILISP_TEST_FILE_PATTERN``.
By default, this value is ``(test_[^.]*|.*_test)\.(lpy|cljc)``.

.. _test_fixtures:

Fixtures
--------

Basilisp supports test fixtures which can serve as setup and teardown functions for either individual tests or for whole test modules.
Fixtures can be applied using the :lpy:fn:`use-fixtures` function.

Basilisp comes with one builtin fixture, which can generate a temporary directory for the duration of the test.

.. code-block:: clojure

   (ns my-project.test-core
     (:require
      [basilisp.test :as test :refer [deftest is are testing]]
      [basilisp.test.fixtures :as fixtures :refer [*tempdir*]))

   (test/use-fixtures :each fixtures/tempdir)

   (deftest some-test
     ;; accessing ``*tempdir*`` here will give a directory that will be
     ;; cleaned up after this test is run
     )

Fixtures can trivially be written by writing a basic function and passing it to ``use-fixtures``.
For fixtures which only need to perform setup, a fixture of no arguments will suffice.
For fixtures which must perform setup and teardown or just teardown, a function of no arguments should be written and it should :lpy:form:`yield` after the setup step and before the teardown.
The test framework will yield control back to the fixture function when it is time to teardown.

You can see below that the fixture uses a :ref:`dynamic Var <dynamic_vars>` to communicate what it has done back to any tests that use this fixture.

.. code-block::

   (def ^:dynamic *tempdir* nil)

   (defn tempdir
     []
     (with-open [d (tempfile/TemporaryDirectory)]
       (binding [*tempdir* d]
         (yield))))

.. warning::

   Basilisp test fixtures are not related to PyTest fixtures and they cannot be used interchangeably.
