from unittest.mock import patch

import pytest

from basilisp.lang import atom as atom
from basilisp.lang import map as lmap
from basilisp.lang import spec
from basilisp.lang import symbol as sym
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
