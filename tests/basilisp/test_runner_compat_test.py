import pytest

from basilisp.lang import keyword as kw
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
               [deftest is run-all-tests run-test-var run-tests successful? use-fixtures]])

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


@pytest.mark.parametrize("fixture_type", ["once", "each"])
def test_fixture_errors_are_reported_in_the_summary(
    runner: CompileFn, cap_lisp_io, fixture_type: str
):
    out, _ = cap_lisp_io
    runner(f"""
        (use-fixtures :{fixture_type}
          (fn []
            (throw (python/Exception "fixture error"))))
        """)

    summary = runner("(run-test-var #'passing-test)")

    assert 0 == _summary_value(summary, "test")
    assert 0 == _summary_value(summary, "pass")
    assert 0 == _summary_value(summary, "fail")
    assert 1 == _summary_value(summary, "error")
    assert runner("(successful? (run-test-var #'passing-test))") is False
    assert "ERROR in test fixture:" in out.getvalue()
