from unittest.mock import patch

import pytest

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
