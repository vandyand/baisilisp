import pytest

from basilisp.lang import keyword as kw
from basilisp.lang import spec as lspec
from basilisp.test.check import _impl as gen_impl


def _k(name):
    return kw.keyword(name)


def test_fspec_generator_returns_callable_that_validates_args_and_ret():
    function_spec = lspec.fspec(
        args=lspec.cat(_k("x"), int, _k("label"), str),
        ret=bool,
    )

    generated = gen_impl.generate(lspec.gen(function_spec), 12, 303)

    assert callable(generated)
    assert lspec.valid(function_spec, generated)
    assert isinstance(generated(42, "ok"), bool)
    with pytest.raises(AssertionError):
        generated("bad", "ok")
    with pytest.raises(AssertionError):
        generated(1)


def test_fspec_generator_without_ret_uses_portable_any_values():
    function_spec = lspec.fspec(args=lspec.cat(_k("x"), int))
    generated = gen_impl.generate(lspec.gen(function_spec), 12, 404)

    assert callable(generated)
    assert generated(1) is not None
    with pytest.raises(AssertionError):
        generated("bad")


def test_fspec_generator_validates_fn_relation_against_conformed_args():
    args_key = _k("args")
    ret_key = _k("ret")
    x_key = _k("x")

    def relation(call):
        args = call.val_at(args_key)
        ret = call.val_at(ret_key)
        return args.val_at(x_key) == 7 and isinstance(ret, int)

    function_spec = lspec.fspec(
        args=lspec.cat(
            x_key, lspec.with_gen(lambda value: value == 7, lambda: gen_impl.return_(7))
        ),
        ret=int,
        fn=relation,
    )
    generated = gen_impl.generate(lspec.gen(function_spec), 20, 91)

    assert isinstance(generated(7), int)
    with pytest.raises(AssertionError):
        generated(6)


def test_fspec_generator_requires_args_spec():
    with pytest.raises(TypeError, match="without :args"):
        lspec.gen(lspec.fspec(ret=int))
