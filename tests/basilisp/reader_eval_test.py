import io

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from basilisp.lang import keyword as kw
from basilisp.lang import reader, runtime
from basilisp.lang import symbol as sym


def test_reader_eval_callback_replaces_nested_forms():
    forms = list(
        reader.read_str(
            "[#=(+ 1 2) {:value #=(+ 3 4)}]",
            reader_eval=lambda form: len(form),
        )
    )

    assert forms[0][0] == 3
    assert forms[0][1].val_at(kw.keyword("value")) == 3


@given(st.integers())
def test_reader_eval_callback_receives_arbitrary_numeric_forms(value):
    assert list(reader.read_str(f"#={value}", reader_eval=lambda form: form)) == [value]


def test_reader_eval_is_disabled_without_an_evaluator_and_preserves_callback_errors():
    with pytest.raises(reader.SyntaxError, match=r"Reader eval \(#=\) is disabled"):
        list(reader.read_str("#=(+ 1 2)"))
    with pytest.raises(ValueError, match="callback failure"):
        list(
            reader.read_str(
                "#=(+ 1 2)",
                reader_eval=lambda _form: (_ for _ in ()).throw(
                    ValueError("callback failure")
                ),
            )
        )
    with pytest.raises(
        reader.UnexpectedEOFError, match="Unexpected EOF after reader eval"
    ):
        list(reader.read_str("#=", reader_eval=lambda form: form))


def test_core_reader_eval_obeys_dynamic_bindings(core_ns):
    read_eval = core_ns.find(sym.symbol("*read-eval*"))
    assert read_eval is not None
    read_string = core_ns.find(sym.symbol("read-string"))
    assert read_string is not None

    assert read_string.value("#=(+ 20 22)") == 42
    with runtime.bindings({read_eval: False}):
        with pytest.raises(reader.SyntaxError, match=r"Reader eval \(#=\) is disabled"):
            read_string.value("#=(+ 20 22)")
    with runtime.bindings({read_eval: kw.keyword("unknown")}):
        with pytest.raises(PermissionError, match=r"\*read-eval\* is :unknown"):
            read_string.value("1")


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    st.integers(min_value=-(10**12), max_value=10**12),
    st.integers(min_value=-(10**12), max_value=10**12),
)
def test_core_reader_eval_evaluates_generated_arithmetic(core_ns, left, right):
    read_string = core_ns.find(sym.symbol("read-string"))
    assert read_string is not None

    assert read_string.value(f"#=(+ {left} {right})") == left + right
