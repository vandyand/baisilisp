from unittest.mock import patch

import pytest
from hypothesis import strategies as st

from basilisp.lang import atom as atom
from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import spec
from basilisp.lang import symbol as sym
from basilisp.lang.exception import ExceptionInfo
from basilisp.lang.runtime import Namespace, Var


@pytest.fixture
def function_var():
    ns_sym = sym.symbol("tests.spec-function")
    with patch(
        "basilisp.lang.runtime.Namespace._NAMESPACES",
        atom.Atom(lmap.map({ns_sym: Namespace(ns_sym)})),
    ):
        yield Var.intern(ns_sym, sym.symbol("identity"), lambda value: value)


def test_fdef_registers_a_callable_descriptor(function_var):
    descriptor = spec.fdef(function_var, args=int, ret=int, fn=lambda _args, _ret: True)

    assert spec.get_fspec(function_var) is descriptor
    assert spec.valid(int, 0)
    assert not spec.valid(int, "0")
    assert spec.valid(descriptor, function_var.root)
    assert not spec.valid(descriptor, 42)


def test_fdef_rejects_non_var_targets():
    with pytest.raises(TypeError, match="Basilisp Vars"):
        spec.fdef(lambda value: value)


def test_instrument_validates_module_and_var_calls_and_restores_bindings(function_var):
    setattr(function_var.ns.module, "identity", function_var.root)
    original = function_var.root
    spec.fdef(
        function_var,
        args=spec.cat(kw.keyword("value"), int),
        ret=int,
    )

    assert spec.instrument(function_var) == (function_var,)
    assert function_var.root is not original
    assert function_var.ns.module.identity(1) == 1
    assert function_var(2) == 2
    with pytest.raises(ExceptionInfo, match=":args") as exc_info:
        function_var.ns.module.identity("invalid")
    assert exc_info.value.data.val_at(
        kw.keyword("target", ns="basilisp.spec.test.alpha")
    ) == ("tests.spec-function/identity")
    assert exc_info.value.data.val_at(kw.keyword("problems", ns="basilisp.spec.alpha"))

    assert spec.unstrument(function_var) == (function_var,)
    assert function_var.root is original
    assert function_var.ns.module.identity is original


def test_unstrument_preserves_a_redefined_var_binding(function_var):
    setattr(function_var.ns.module, "identity", function_var.root)
    spec.fdef(function_var, args=spec.cat(kw.keyword("value"), int), ret=int)
    spec.instrument(function_var)

    replacement = lambda value: value * 2
    function_var.bind_root(replacement)
    function_var.ns.module.identity = replacement

    spec.unstrument(function_var)

    assert function_var.root is replacement
    assert function_var.ns.module.identity is replacement


def test_instrument_rejects_dynamic_vars_and_keyword_calls(function_var):
    setattr(function_var.ns.module, "identity", function_var.root)
    spec.fdef(function_var, args=spec.cat(kw.keyword("value"), int), ret=int)
    spec.instrument(function_var)
    try:
        with pytest.raises(ExceptionInfo, match="keyword arguments"):
            function_var.ns.module.identity(value=1)
    finally:
        spec.unstrument(function_var)

    dynamic_var = Var.intern(
        function_var.ns,
        sym.symbol("dynamic-identity"),
        lambda value: value,
        dynamic=True,
    )
    spec.fdef(dynamic_var, args=spec.cat(kw.keyword("value"), int), ret=int)
    with pytest.raises(TypeError, match="dynamic Vars"):
        spec.instrument(dynamic_var)


def test_instrument_preflight_does_not_partially_wrap_a_batch(function_var):
    setattr(function_var.ns.module, "identity", function_var.root)
    original = function_var.root
    spec.fdef(function_var, args=spec.cat(kw.keyword("value"), int), ret=int)
    dynamic_var = Var.intern(
        function_var.ns,
        sym.symbol("dynamic-identity"),
        lambda value: value,
        dynamic=True,
    )
    spec.fdef(dynamic_var, args=spec.cat(kw.keyword("value"), int), ret=int)

    with pytest.raises(TypeError, match="dynamic Vars"):
        spec.instrument(function_var, dynamic_var)

    assert function_var.root is original
    assert function_var.ns.module.identity is original


def test_check_generates_known_values_and_reports_contract_failures(function_var):
    spec.fdef(function_var, args=spec.cat(kw.keyword("value"), int), ret=int)

    passed = spec.check(function_var, num_tests=20, seed=17)[0]

    assert passed.val_at(kw.keyword("pass?", ns="basilisp.spec.test.alpha"))
    assert passed.val_at(kw.keyword("num-tests", ns="basilisp.spec.test.alpha")) == 20

    broken = Var.intern(
        function_var.ns,
        sym.symbol("broken"),
        lambda _value: "not an integer",
    )
    spec.fdef(broken, args=spec.cat(kw.keyword("value"), int), ret=int)

    failed = spec.check(broken, num_tests=20, seed=17)[0]

    assert not failed.val_at(kw.keyword("pass?", ns="basilisp.spec.test.alpha"))
    assert isinstance(
        failed.val_at(kw.keyword("failure", ns="basilisp.spec.test.alpha")),
        ExceptionInfo,
    )


def test_check_accepts_explicit_generators_and_rejects_unknown_predicates(function_var):
    even = lambda value: value % 2 == 0
    generated_even = spec.with_gen(even, st.integers().map(lambda value: value * 2))
    assert spec.valid(generated_even, 2)
    assert not spec.valid(generated_even, 3)
    assert spec.unform(generated_even, 2) == 2
    spec.fdef(
        function_var,
        args=spec.cat(
            kw.keyword("value"),
            generated_even,
        ),
        ret=int,
    )

    assert spec.check(function_var, num_tests=20, seed=3)[0].val_at(
        kw.keyword("pass?", ns="basilisp.spec.test.alpha")
    )

    spec.fdef(function_var, args=spec.cat(kw.keyword("value"), even), ret=int)
    with pytest.raises(TypeError, match="with-gen"):
        spec.check(function_var, num_tests=1)


def test_check_generates_map_of_and_keys_descriptors(function_var):
    spec.fdef(
        function_var,
        args=spec.cat(kw.keyword("value"), spec.map_of(str, int)),
        ret=dict,
    )
    assert spec.check(function_var, num_tests=20, seed=19)[0].val_at(
        kw.keyword("pass?", ns="basilisp.spec.test.alpha")
    )

    name = kw.keyword("name", ns="tests.generated")
    count = kw.keyword("count", ns="tests.generated")
    spec.define(name, str)
    spec.define(count, int)
    spec.fdef(
        function_var,
        args=spec.cat(kw.keyword("value"), spec.keys([name], [count])),
        ret=dict,
    )
    assert spec.check(function_var, num_tests=20, seed=23)[0].val_at(
        kw.keyword("pass?", ns="basilisp.spec.test.alpha")
    )


def test_check_rejects_undefined_keyword_and_empty_set_domains(function_var):
    undefined = kw.keyword("undefined", ns="tests.generated")
    spec.fdef(function_var, args=spec.cat(kw.keyword("value"), undefined), ret=int)
    with pytest.raises(TypeError, match="undefined spec"):
        spec.check(function_var, num_tests=1)

    spec.fdef(function_var, args=spec.cat(kw.keyword("value"), set()), ret=int)
    with pytest.raises(TypeError, match="empty set"):
        spec.check(function_var, num_tests=1)
