import random

import pytest

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import runtime
from basilisp.lang import symbol as sym
from tests.basilisp.helpers import CompileFn


@pytest.fixture
def test_ns() -> str:
    return "basilisp.test-runner-compat"


@pytest.fixture
def compiler_file_path() -> str:
    return "<basilisp.test runner compatibility test>"


@pytest.fixture
def runner(lcompile: CompileFn) -> CompileFn:
    lcompile("""
    (require '[basilisp.test :refer
               [assert-expr deftest deftest- do-report is run-all-tests run-test-var
                run-tests set-test successful? use-fixtures with-test]])

    (def events (atom []))

    (defn once-fixture []
      (swap! events conj :once-before)
      (yield)
      (swap! events conj :once-after))

    (defn each-fixture []
      (swap! events conj :each-before)
      (yield)
      (swap! events conj :each-after))

    (use-fixtures :once once-fixture)
    (use-fixtures :each each-fixture)

    (deftest passing-test
      (is true)
      (is (= 1 1)))

    (deftest failing-test
      (is false))

    (deftest error-test
      (throw (python/Exception "uncaught test error")))
    """)
    return lcompile


def _summary_value(summary, name: str) -> int:
    return summary.val_at(kw.keyword(name))


def test_run_test_var_uses_namespace_fixtures(runner: CompileFn):
    summary = runner("(run-test-var #'passing-test)")

    assert 1 == _summary_value(summary, "test")
    assert 2 == _summary_value(summary, "pass")
    assert 0 == _summary_value(summary, "fail")
    assert 0 == _summary_value(summary, "error")
    assert kw.keyword("summary") == summary.val_at(kw.keyword("type"))
    assert list(runner("@events")) == [
        kw.keyword("once-before"),
        kw.keyword("each-before"),
        kw.keyword("each-after"),
        kw.keyword("once-after"),
    ]


def test_run_tests_counts_assertion_failures_errors_and_fixtures(
    runner: CompileFn, cap_lisp_io
):
    out, _ = cap_lisp_io
    summary = runner("(run-tests 'basilisp.test-runner-compat)")

    assert 3 == _summary_value(summary, "test")
    assert 2 == _summary_value(summary, "pass")
    assert 1 == _summary_value(summary, "fail")
    assert 1 == _summary_value(summary, "error")
    assert "Testing basilisp.test-runner-compat" in out.getvalue()
    assert "FAIL in (failing-test)" in out.getvalue()
    assert "expected: (not false)" in out.getvalue()
    assert "ERROR in (error-test)" in out.getvalue()
    assert "Ran 3 tests containing 4 assertions." in out.getvalue()
    assert runner("(successful? (run-test-var #'passing-test))") is True
    assert runner("(successful? (run-test-var #'failing-test))") is False
    assert list(runner("@events")) == [
        kw.keyword("once-before"),
        kw.keyword("each-before"),
        kw.keyword("each-after"),
        kw.keyword("each-before"),
        kw.keyword("each-after"),
        kw.keyword("each-before"),
        kw.keyword("each-after"),
        kw.keyword("once-after"),
        kw.keyword("once-before"),
        kw.keyword("each-before"),
        kw.keyword("each-after"),
        kw.keyword("once-after"),
        kw.keyword("once-before"),
        kw.keyword("each-before"),
        kw.keyword("each-after"),
        kw.keyword("once-after"),
    ]


def test_run_all_tests_filters_loaded_namespaces(runner: CompileFn):
    summary = runner('(run-all-tests #"basilisp\\.test-runner-compat")')

    assert 3 == _summary_value(summary, "test")
    assert 2 == _summary_value(summary, "pass")
    assert 1 == _summary_value(summary, "fail")
    assert 1 == _summary_value(summary, "error")


def test_run_all_tests_with_no_matching_namespaces_returns_empty_summary(
    runner: CompileFn,
):
    summary = runner('(run-all-tests #"does-not-match")')

    assert 0 == _summary_value(summary, "test")
    assert 0 == _summary_value(summary, "pass")
    assert 0 == _summary_value(summary, "fail")
    assert 0 == _summary_value(summary, "error")


@pytest.mark.parametrize(
    ("fixture_type", "phase", "expected"),
    [
        ("once", "setup", {"test": 0, "pass": 0, "fail": 0, "error": 1}),
        ("each", "setup", {"test": 0, "pass": 0, "fail": 0, "error": 1}),
        ("once", "teardown", {"test": 1, "pass": 2, "fail": 0, "error": 1}),
        ("each", "teardown", {"test": 1, "pass": 2, "fail": 0, "error": 1}),
    ],
)
def test_fixture_errors_are_reported_in_the_summary(
    runner: CompileFn, cap_lisp_io, fixture_type: str, phase: str, expected: dict
):
    out, _ = cap_lisp_io
    fixture_body = (
        '(throw (python/Exception "fixture error"))'
        if phase == "setup"
        else '(yield)\n            (throw (python/Exception "fixture error"))'
    )
    runner(f"""
        (use-fixtures :{fixture_type}
          (fn []
            {fixture_body}))
        """)

    summary = runner("(run-test-var #'passing-test)")

    assert {
        name: _summary_value(summary, name)
        for name in ("test", "pass", "fail", "error")
    } == expected
    assert runner("(successful? (run-test-var #'passing-test))") is False
    assert "ERROR in test fixture:" in out.getvalue()


def test_runner_repeated_mixed_result_stress(runner: CompileFn, cap_lisp_io):
    rng = random.Random(0xB45115)
    expected = {"test": 3, "pass": 2, "fail": 1, "error": 1}
    forms = []

    for index in range(120):
        outcome = rng.choice(("pass", "pass", "failure", "error"))
        name = f"generated-test-{index}"
        expected["test"] += 1

        if outcome == "pass":
            expected["pass"] += 2
            forms.append(f"""
                (deftest {name}
                  (is true)
                  (is (= {index} {index})))
                """)
        elif outcome == "failure":
            expected["fail"] += 1
            forms.append(f"""
                (deftest {name}
                  (is false))
                """)
        else:
            expected["error"] += 1
            forms.append(f"""
                (deftest {name}
                  (throw (python/Exception "generated error {index}")))
                """)

    runner("\n".join(forms))

    for _ in range(5):
        summary = runner("(run-tests 'basilisp.test-runner-compat)")
        assert {
            name: _summary_value(summary, name)
            for name in ("test", "pass", "fail", "error")
        } == expected


def test_custom_assertions_and_metadata_backed_tests(runner: CompileFn):
    runner("""
    (defmethod assert-expr 'is-even? [msg form]
      `(let [value# ~(second form)]
         (do-report {:type (if (zero? (mod value# 2)) :pass :fail)
                     :message ~msg
                     :expr (quote ~form)
                     :actual value#
                     :expected :even})))

    (deftest custom-assertion-test
      (is (is-even? 4)))

    (deftest- private-test
      (is true))

    (with-test (defn with-tested [] :value)
      (is (= :value (with-tested))))

    (defn set-tested [] :set-value)
    (set-test set-tested
      (is (= :set-value (set-tested))))
    """)

    summary = runner("(run-tests 'basilisp.test-runner-compat)")

    assert 7 == _summary_value(summary, "test")
    assert 6 == _summary_value(summary, "pass")
    assert 1 == _summary_value(summary, "fail")
    assert 1 == _summary_value(summary, "error")


def test_load_tests_can_omit_test_definitions(runner: CompileFn):
    load_tests = runtime.Var.find(sym.symbol("*load-tests*", ns="basilisp.test"))
    assert load_tests is not None

    with runtime.bindings(lmap.map({load_tests: False})):
        runner("(deftest omitted-test (is false))")

    assert runner("(find-var 'basilisp.test-runner-compat/omitted-test)") is None
