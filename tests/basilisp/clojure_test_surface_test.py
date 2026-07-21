import random

import pytest

from basilisp.lang import keyword as kw
from basilisp.lang import runtime
from basilisp.lang import symbol as sym
from tests.basilisp.helpers import CompileFn


@pytest.fixture
def test_ns() -> str:
    return "basilisp.clojure-test-surface"


@pytest.fixture
def compiler_file_path() -> str:
    return "<clojure.test public surface compatibility test>"


@pytest.fixture
def runner(lcompile: CompileFn) -> CompileFn:
    lcompile("""
        (require '[clojure.test :refer :all])

        (deftest passing
          (is true)
          (is (odd? 3)))

        (deftest failing
          (is false))

        (deftest exploding
          (throw (python/Exception "uncaught")))
        """)
    return lcompile


def _counter_values(value) -> dict[str, int]:
    return {
        name: value.val_at(kw.keyword(name))
        for name in ("test", "pass", "fail", "error")
    }


@pytest.mark.parametrize(
    ("var_name", "expected"),
    [
        ("passing", {"test": 1, "pass": 2, "fail": 0, "error": 0}),
        ("failing", {"test": 1, "pass": 0, "fail": 1, "error": 0}),
        ("exploding", {"test": 1, "pass": 0, "fail": 0, "error": 1}),
    ],
)
def test_test_var_matches_clojure_style_report_counters(
    runner: CompileFn, var_name: str, expected: dict[str, int]
):
    counters = runner(f"""
        (binding [*report-counters* (ref *initial-report-counters*)]
          (test-var #'{var_name})
          @*report-counters*)
        """)

    assert expected == _counter_values(counters)


def test_deftest_exposes_standard_test_metadata_and_core_test(runner: CompileFn):
    assert runner("(fn? (:test (meta #'passing)))") is True
    assert runner("(test #'passing)") == kw.keyword("ok")


def test_assertion_extension_helpers_return_test_values_and_report_errors(
    runner: CompileFn,
):
    assert runner("(eval (assert-any nil true))") is True
    assert runner("(eval (assert-any nil false))") is False
    assert runner("(eval (assert-predicate nil '(odd? 5)))") is True
    assert runner("(eval (assert-predicate nil '(odd? 4)))") is False

    counters = runner("""
        (binding [*report-counters* (ref *initial-report-counters*)]
          (try-expr "division" (/ 1 0))
          @*report-counters*)
        """)
    assert {"test": 0, "pass": 0, "fail": 0, "error": 1} == _counter_values(counters)


def test_output_unbound_var_function_and_source_helpers(runner: CompileFn):
    assert runner("""
        (let [writer (io/StringIO)]
          (binding [*test-out* writer]
            (with-test-out (println "redirected")))
          (.getvalue writer))
        """).replace("\r\n", "\n") == "redirected\n"
    assert runner("(function? 'odd?)") is True
    assert runner("(function? 'deftest)") is False
    assert runner("(function? 42)") is False
    assert (
        runner(
            "(do (declare temporarily-unbound) (nil? (get-possibly-unbound-var #'temporarily-unbound)))"
        )
        is True
    )

    position = runner("(file-position 0)")
    assert isinstance(position[0], str)
    assert isinstance(position[1], int)


def test_seeded_report_counter_stress_isolated_between_runs(runner: CompileFn):
    randomizer = random.Random(20260729)
    forms = []
    expected = {"test": 0, "pass": 0, "fail": 0, "error": 0}
    for index in range(180):
        outcome = randomizer.choice(("pass", "pass", "fail", "error"))
        name = f"generated_{index}"
        expected["test"] += 1
        if outcome == "pass":
            expected["pass"] += 1
            body = "(is true)"
        elif outcome == "fail":
            expected["fail"] += 1
            body = "(is false)"
        else:
            expected["error"] += 1
            body = '(throw (python/Exception "generated"))'
        forms.append(f"(deftest {name} {body})")
    runner("\n".join(forms))

    for _ in range(4):
        counters = runner("""
            (binding [*report-counters* (ref *initial-report-counters*)]
              (doseq [v (vals (ns-interns *ns*))]
                (when (.startswith (str (:name (meta v))) "generated_")
                  (test-var v)))
              @*report-counters*)
            """)
        assert expected == _counter_values(counters)
