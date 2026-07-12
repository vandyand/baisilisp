import sys

from basilisp.lang import compiler as compiler
from basilisp.lang import reader, runtime
from basilisp.lang import symbol as sym
from tests.basilisp.helpers import get_or_create_ns


def test_tap_reports_fixture_errors_and_keeps_tap_output_parseable():
    ns_name = "basilisp.test-tap-fixtures"
    ns = get_or_create_ns(sym.symbol(ns_name))
    context = compiler.CompilerContext("<tap fixture test>")
    source = """
    (require '[basilisp.test :as t]
             '[basilisp.test.tap :as tap])

    (t/use-fixtures :each
      (fn []
        (throw (python/Exception "fixture exploded"))))

    (t/deftest fixture-test
      (t/is true))

    (with-out-str
      (tap/with-tap-output
        (t/run-tests 'basilisp.test-tap-fixtures)))
    """
    try:
        with runtime.ns_bindings(ns_name):
            sys.modules[ns.module.__name__] = ns.module
            try:
                for form in reader.read_str(source):
                    result = compiler.compile_and_exec_form(form, context, ns)
            finally:
                del sys.modules[ns.module.__name__]
    finally:
        runtime.Namespace.remove(sym.symbol(ns_name))

    assert isinstance(result, str)
    assert "not ok fixture" in result
    assert "# fixture exploded" in result
    assert "1..1" in result
    assert "ERROR in test fixture" not in result
    assert "Testing basilisp.test-tap-fixtures" not in result
