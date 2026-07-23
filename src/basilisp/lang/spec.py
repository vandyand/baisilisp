"""Portable descriptor-based validation used by ``basilisp.spec.alpha``."""

from __future__ import annotations

import datetime as _datetime
import functools
import io
import math
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from basilisp.lang import keyword as kw
from basilisp.lang import list as llist
from basilisp.lang import map as lmap
from basilisp.lang import symbol as sym
from basilisp.lang import vector as vec
from basilisp.lang.exception import ExceptionInfo
from basilisp.lang.interfaces import IPersistentMap, IPersistentSet, ISequential
from basilisp.lang.runtime import Var
from basilisp.lang.util import munge

INVALID = kw.keyword("invalid", ns="basilisp.spec.alpha")
_PROBLEMS = kw.keyword("problems", ns="basilisp.spec.alpha")
_PATH = kw.keyword("path")
_PRED = kw.keyword("pred")
_VAL = kw.keyword("val")
_VIA = kw.keyword("via")
_IN = kw.keyword("in")
_REGISTRY: dict[kw.Keyword, Any] = {}
_FUNCTION_SPECS: dict[Any, "_FSpec"] = {}
_INSTRUMENTED: dict[Var, "_Instrumented"] = {}
_REGISTRY_LOCK = threading.RLock()
_MISSING = object()

_CALL_ARGS = kw.keyword("args")
_CALL_RET = kw.keyword("ret")
_CALL_TARGET = kw.keyword("target", ns="basilisp.spec.test.alpha")
_CALL_KEYWORD_ARGS = kw.keyword("keyword-args", ns="basilisp.spec.test.alpha")
_CHECK_PASS = kw.keyword("pass?", ns="basilisp.spec.test.alpha")
_CHECK_FAILURE = kw.keyword("failure", ns="basilisp.spec.test.alpha")
_CHECK_NUM_TESTS = kw.keyword("num-tests", ns="basilisp.spec.test.alpha")
_ASSERTION_FAILED = kw.keyword("assertion-failed", ns="basilisp.spec.alpha")
_FAILURE = kw.keyword("failure", ns="basilisp.spec.alpha")
_CHECK_ASSERTS = False
_ASSERT_LOCK = threading.RLock()


class _Spec:
    pass


class _Regex(_Spec):
    pass


@dataclass(frozen=True)
class _FSpec(_Spec):
    args: Any | None = None
    ret: Any | None = None
    fn: Any | None = None


@dataclass(frozen=True)
class _WithGen(_Spec):
    spec: Any
    generator: Any


@dataclass(frozen=True)
class _PredicateSpec(_Spec):
    predicate: Any


@dataclass(frozen=True)
class _Conformer(_Spec):
    conformer: Callable[[Any], Any]
    unformer: Callable[[Any], Any] | None = None


@dataclass(frozen=True)
class _Nonconforming(_Spec):
    spec: Any


@dataclass(frozen=True)
class _Merge(_Spec):
    specs: tuple[Any, ...]


@dataclass(frozen=True)
class _Instrumented:
    original: Callable[..., Any]
    module_name: str
    module_value: Any
    wrapper: Callable[..., Any]


class _GeneratedFSpecFunction:
    __slots__ = (
        "_args_spec",
        "_ret_spec",
        "_fn_spec",
        "_ret_generator",
        "_lock",
        "_calls",
    )

    def __init__(
        self,
        args_spec: Any,
        ret_spec: Any | None,
        fn_spec: Any | None,
        ret_generator: Any,
    ) -> None:
        self._args_spec = args_spec
        self._ret_spec = ret_spec
        self._fn_spec = fn_spec
        self._ret_generator = ret_generator
        self._lock = threading.Lock()
        self._calls = 0

    def _next_seed(self) -> int:
        with self._lock:
            self._calls += 1
            return 0xF5FEC ^ self._calls

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if kwargs:
            raise AssertionError("generated fspec functions do not accept kwargs")
        call_args = vec.v(*args)
        conformed_args = _conform(self._args_spec, call_args, (), (), (), None)
        if conformed_args is INVALID:
            raise AssertionError(explain_str(self._args_spec, call_args))

        impl = _test_check_impl()
        ret_generator = self._ret_generator
        if self._fn_spec is not None:
            ret_generator = impl.such_that(
                lambda value: valid(
                    self._fn_spec,
                    lmap.map({_CALL_ARGS: conformed_args, _CALL_RET: value}),
                ),
                ret_generator,
                {"max-tries": 100},
            )
        ret = impl.generate(ret_generator, 30, self._next_seed())
        if self._ret_spec is not None and not valid(self._ret_spec, ret):
            raise AssertionError(explain_str(self._ret_spec, ret))
        if self._fn_spec is not None and not valid(
            self._fn_spec, lmap.map({_CALL_ARGS: conformed_args, _CALL_RET: ret})
        ):
            raise AssertionError(
                explain_str(
                    self._fn_spec,
                    lmap.map({_CALL_ARGS: conformed_args, _CALL_RET: ret}),
                )
            )
        return ret


@dataclass(frozen=True)
class _And(_Spec):
    specs: tuple[Any, ...]


@dataclass(frozen=True)
class _Or(_Spec):
    branches: tuple[tuple[kw.Keyword, Any], ...]


@dataclass(frozen=True)
class _Nilable(_Spec):
    spec: Any


@dataclass(frozen=True)
class _CollOf(_Spec):
    spec: Any
    kind: Any | None = None
    count: int | None = None
    min_count: int | None = None
    max_count: int | None = None
    distinct: bool = False


@dataclass(frozen=True)
class _MapOf(_Spec):
    key_spec: Any
    value_spec: Any


@dataclass(frozen=True)
class _Keys(_Spec):
    required: tuple[tuple[kw.Keyword, kw.Keyword], ...]
    optional: tuple[tuple[kw.Keyword, kw.Keyword], ...]


@dataclass(frozen=True)
class _KeysStar(_Regex):
    map_spec: _Keys


@dataclass(frozen=True)
class _Tuple(_Spec):
    specs: tuple[Any, ...]


@dataclass(frozen=True)
class _MultiSpec(_Spec):
    dispatch: Callable[[Any], Any]
    retag: Any | None = None


@dataclass(frozen=True)
class _Cat(_Regex):
    branches: tuple[tuple[kw.Keyword, Any], ...]


@dataclass(frozen=True)
class _Alt(_Regex):
    branches: tuple[tuple[kw.Keyword, Any], ...]


@dataclass(frozen=True)
class _Repeat(_Regex):
    spec: Any
    minimum: int


@dataclass(frozen=True)
class _Maybe(_Regex):
    spec: Any


@dataclass(frozen=True)
class _Amp(_Regex):
    spec: Any
    predicates: tuple[Any, ...]


def define(key: kw.Keyword, spec: Any) -> kw.Keyword:
    if not isinstance(key, kw.Keyword):
        raise TypeError("spec names must be keywords")
    with _REGISTRY_LOCK:
        _REGISTRY[key] = spec
    return key


def get_spec(key: kw.Keyword) -> Any | None:
    with _REGISTRY_LOCK:
        return _REGISTRY.get(key)


def registry() -> IPersistentMap:
    """Return a snapshot of the registered named specs."""
    with _REGISTRY_LOCK:
        return lmap.map(dict(_REGISTRY))


def fspec(
    *, args: Any | None = None, ret: Any | None = None, fn: Any | None = None
) -> _FSpec:
    """Create a descriptor for a callable's argument, return, and relation specs."""
    return _FSpec(args, ret, fn)


def with_gen(spec: Any, generator: Any) -> _WithGen:
    """Attach an explicit generator or generator factory to ``spec``.

    ``s/gen`` consumes portable test.check generators, while
    ``basilisp.spec.test.alpha/check`` consumes Hypothesis strategies. Keeping
    the descriptor neutral lets the same ``with-gen`` form serve each public
    API without making validation itself depend on either generator engine.
    """
    return _WithGen(spec, generator)


def spec(predicate: Any, generator: Any | None = None) -> _Spec:
    """Create a first-class spec from a predicate or existing descriptor.

    Raw predicates remain valid specs throughout Basilisp; this constructor is
    useful when a library specifically needs a spec value (for ``spec?`` or a
    supplied generator) rather than relying on that implicit coercion.
    """
    descriptor: Any = (
        predicate if isinstance(predicate, _Spec) else _PredicateSpec(predicate)
    )
    return descriptor if generator is None else _WithGen(descriptor, generator)


def spec_q(value: Any) -> Any | None:
    """Return a first-class spec value, or ``None`` when ``value`` is not one."""
    return value if isinstance(value, _Spec) and not isinstance(value, _Regex) else None


def regex_q(value: Any) -> Any | None:
    """Return a regex spec value, or ``None`` when ``value`` is not one."""
    return value if isinstance(value, _Regex) else None


def invalid_q(value: Any) -> bool:
    return value is INVALID


def conformer(
    conform_fn: Callable[[Any], Any], unform_fn: Callable[[Any], Any] | None = None
) -> _Conformer:
    if not callable(conform_fn):
        raise TypeError("conformer requires a callable conform function")
    if unform_fn is not None and not callable(unform_fn):
        raise TypeError("conformer unform function must be callable")
    return _Conformer(conform_fn, unform_fn)


def nonconforming(spec_: Any) -> _Nonconforming:
    return _Nonconforming(spec_)


def merge_(*specs: Any) -> _Merge:
    if not specs:
        raise ValueError("merge requires at least one map spec")
    return _Merge(tuple(specs))


def every(
    spec_: Any,
    *,
    kind: Any | None = None,
    count: int | None = None,
    min_count: int | None = None,
    max_count: int | None = None,
    distinct: bool = False,
) -> _CollOf:
    """Portable ``s/every`` using the same collection semantics as ``coll-of``."""
    return coll_of(
        spec_,
        kind=kind,
        count=count,
        min_count=min_count,
        max_count=max_count,
        distinct=distinct,
    )


def every_kv(key_spec: Any, value_spec: Any) -> _MapOf:
    """Portable ``s/every-kv`` alias for a map-of descriptor."""
    return map_of(key_spec, value_spec)


def int_in_range_q(start: int, end: int, value: Any) -> bool:
    return type(value) is int and start <= value < end


def int_in(start: int, end: int) -> _WithGen:
    """Return a spec for integers in the half-open range ``[start, end)``."""
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not all(isinstance(value, int) for value in (start, end))
    ):
        raise TypeError("int-in bounds must be integers")
    if start >= end:
        raise ValueError("int-in start must be less than end")
    predicate = _PredicateSpec(lambda value: int_in_range_q(start, end, value))
    return _WithGen(
        predicate,
        lambda: _test_check_impl().large_integer_star({"min": start, "max": end - 1}),
    )


def double_in(
    *,
    infinite: bool = True,
    nan: bool = True,
    min_value: float | None = None,
    max_value: float | None = None,
) -> _WithGen:
    """Return a floating-point spec with Clojure ``double-in``-style bounds."""
    if min_value is not None and max_value is not None and min_value > max_value:
        raise ValueError("double-in minimum must not exceed maximum")

    def valid_double(value: Any) -> bool:
        if type(value) is not float:
            return False
        if not infinite and math.isinf(value):
            return False
        if not nan and math.isnan(value):
            return False
        return (min_value is None or value >= min_value) and (
            max_value is None or value <= max_value
        )

    options: dict[str, Any] = {"infinite?": infinite, "NaN?": nan}
    if min_value is not None:
        options["min"] = min_value
    if max_value is not None:
        options["max"] = max_value
    return _WithGen(
        _PredicateSpec(valid_double), lambda: _test_check_impl().double_star(options)
    )


def _instant_millis(value: _datetime.datetime) -> int:
    epoch = _datetime.datetime(1970, 1, 1, tzinfo=value.tzinfo)
    return int((value - epoch).total_seconds() * 1000)


def inst_in_range_q(
    start: _datetime.datetime, end: _datetime.datetime, value: Any
) -> bool:
    return isinstance(value, _datetime.datetime) and start <= value < end


def inst_in(start: _datetime.datetime, end: _datetime.datetime) -> _WithGen:
    """Return an instant spec for the half-open range ``[start, end)``."""
    if not isinstance(start, _datetime.datetime) or not isinstance(
        end, _datetime.datetime
    ):
        raise TypeError("inst-in bounds must be datetime values")
    if start >= end:
        raise ValueError("inst-in start must be less than end")
    lower, upper = _instant_millis(start), _instant_millis(end) - 1
    epoch = _datetime.datetime(1970, 1, 1, tzinfo=start.tzinfo)
    predicate = _PredicateSpec(lambda value: inst_in_range_q(start, end, value))
    return _WithGen(
        predicate,
        lambda: _test_check_impl().fmap(
            lambda millis: epoch + _datetime.timedelta(milliseconds=millis),
            _test_check_impl().large_integer_star({"min": lower, "max": upper}),
        ),
    )


def check_asserts_q() -> bool:
    with _ASSERT_LOCK:
        return _CHECK_ASSERTS


def check_asserts(enabled: Any) -> bool:
    """Enable or disable runtime ``s/assert`` validation and return its state."""
    global _CHECK_ASSERTS
    with _ASSERT_LOCK:
        _CHECK_ASSERTS = bool(enabled)
        return _CHECK_ASSERTS


def assert_(spec_: Any, value: Any) -> Any:
    """Validate and return ``value`` when runtime spec assertions are enabled."""
    if not check_asserts_q() or valid(spec_, value):
        return value
    data = explain_data(spec_, value)
    assert data is not None
    failure_data = data.assoc(_FAILURE, _ASSERTION_FAILED)
    raise ExceptionInfo(
        f"Spec assertion failed\n{explain_str(spec_, value)}", failure_data
    )


def fdef(
    target: Any,
    *,
    args: Any | None = None,
    ret: Any | None = None,
    fn: Any | None = None,
) -> _FSpec:
    """Register and return a function spec for a Basilisp Var."""
    if not isinstance(target, Var):
        raise TypeError("fdef targets must be Basilisp Vars")
    spec = fspec(args=args, ret=ret, fn=fn)
    with _REGISTRY_LOCK:
        _FUNCTION_SPECS[target] = spec
    return spec


def get_fspec(target: Any) -> _FSpec | None:
    with _REGISTRY_LOCK:
        return _FUNCTION_SPECS.get(target)


def instrument(*targets: Var) -> tuple[Var, ...]:
    """Instrument registered, non-dynamic Basilisp Vars in place.

    Calls routed through a Var or through its current namespace module binding are
    validated against the registered ``:args``, ``:ret``, and ``:fn`` specs.
    Existing references to the original callable are deliberately not patched.
    """
    with _REGISTRY_LOCK:
        selected = targets or tuple(_FUNCTION_SPECS)
        for target in selected:
            _validate_instrument_target(target)
        for target in selected:
            _instrument(target)
        return tuple(selected)


def unstrument(*targets: Var) -> tuple[Var, ...]:
    """Restore the bindings changed by :func:`instrument` when still installed."""
    with _REGISTRY_LOCK:
        selected = targets or tuple(_INSTRUMENTED)
        for target in selected:
            _unstrument(target)
        return tuple(selected)


def check(
    *targets: Var, num_tests: int = 100, seed: int | None = None
) -> tuple[IPersistentMap, ...]:
    """Run generated checks for registered function specs using Hypothesis.

    Only descriptors with a known native generation strategy are supported. Wrap
    arbitrary predicate specs with :func:`with_gen` to provide a strategy.
    """
    if isinstance(num_tests, bool) or not isinstance(num_tests, int) or num_tests < 1:
        raise ValueError("num_tests must be a positive integer")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise TypeError("seed must be an integer or None")

    with _REGISTRY_LOCK:
        selected = targets or tuple(_FUNCTION_SPECS)
        return tuple(_check_function(target, num_tests, seed) for target in selected)


def _check_function(target: Var, num_tests: int, seed: int | None) -> IPersistentMap:
    if not isinstance(target, Var):
        raise TypeError("check targets must be Basilisp Vars")
    if target.dynamic:
        raise TypeError("cannot generate checks for dynamic Vars")

    function_spec = _FUNCTION_SPECS.get(target)
    if function_spec is None:
        raise ValueError("cannot check a Var without an fdef")
    if function_spec.args is None:
        raise ValueError("cannot generate checks without an fdef :args spec")

    argument_strategy = _strategy_for_regex(function_spec.args)
    original = _INSTRUMENTED.get(target, None)
    callable_target = original.original if original is not None else target.root
    if not callable(callable_target):
        raise TypeError("can only generate checks for Vars with callable roots")

    try:
        from hypothesis import given
        from hypothesis import seed as hypothesis_seed
        from hypothesis import settings
    except ImportError as exc:  # pragma: no cover - development dependency
        raise RuntimeError(
            "generated function checks require the optional Hypothesis dependency"
        ) from exc

    @given(argument_strategy)
    @settings(
        database=None, deadline=None, derandomize=seed is None, max_examples=num_tests
    )
    def check_one(call_args: vec.PersistentVector) -> None:
        conformed_args = conform(function_spec.args, call_args)
        if conformed_args is INVALID:
            raise AssertionError(explain_str(function_spec.args, call_args))
        result = callable_target(*call_args)
        if function_spec.ret is not None:
            _validate_function_value(target, ":ret", function_spec.ret, result)
        if function_spec.fn is not None:
            _validate_function_value(
                target,
                ":fn",
                function_spec.fn,
                lmap.map({_CALL_ARGS: conformed_args, _CALL_RET: result}),
            )

    if seed is not None:
        check_one = hypothesis_seed(seed)(check_one)

    try:
        check_one()
    except Exception as exc:  # Hypothesis reraises the minimized failure.
        return lmap.map(
            {
                _CALL_TARGET: _var_symbol(target),
                _CHECK_PASS: False,
                _CHECK_NUM_TESTS: num_tests,
                _CHECK_FAILURE: exc,
            }
        )
    return lmap.map(
        {
            _CALL_TARGET: _var_symbol(target),
            _CHECK_PASS: True,
            _CHECK_NUM_TESTS: num_tests,
        }
    )


def _strategy_for_regex(spec: Any) -> Any:
    values = _strategy_for_regex_values(spec)
    return values.map(lambda generated: vec.v(*generated))


def _strategy_for_regex_values(spec: Any) -> Any:
    strategies = _hypothesis_strategies()
    if isinstance(spec, _WithGen):
        generated = _resolve_strategy(spec.generator)
        return (
            generated
            if isinstance(spec.spec, _Regex)
            else generated.map(lambda value: (value,))
        )
    if isinstance(spec, kw.Keyword):
        resolved = get_spec(spec)
        if resolved is None:
            raise TypeError(f"cannot generate values for undefined spec {spec}")
        return _strategy_for_regex_values(resolved)
    if isinstance(spec, _Cat):
        return strategies.tuples(
            *(_strategy_for_regex_values(child) for _tag, child in spec.branches)
        ).map(_flatten_generated_values)
    if isinstance(spec, _Alt):
        return strategies.one_of(
            *(_strategy_for_regex_values(child) for _tag, child in spec.branches)
        )
    if isinstance(spec, _Repeat):
        return strategies.lists(
            _strategy_for_regex_values(spec.spec), min_size=spec.minimum, max_size=8
        ).map(_flatten_generated_values)
    if isinstance(spec, _Maybe):
        return strategies.one_of(
            strategies.just(()), _strategy_for_regex_values(spec.spec)
        )
    if isinstance(spec, _Amp):
        raise TypeError("cannot generate values for s/&; wrap it with with-gen")
    return _strategy_for_value(spec).map(lambda value: (value,))


def _strategy_for_value(spec: Any) -> Any:
    strategies = _hypothesis_strategies()
    if isinstance(spec, _WithGen):
        return _resolve_strategy(spec.generator)
    if isinstance(spec, _PredicateSpec):
        return _strategy_for_value(spec.predicate)
    if isinstance(spec, _Nonconforming):
        return _strategy_for_value(spec.spec)
    if isinstance(spec, _Merge):
        return strategies.tuples(
            *(_strategy_for_value(child) for child in spec.specs)
        ).map(_merge_maps)
    if isinstance(spec, _Conformer):
        raise TypeError("cannot generate values for conformer; wrap it with with-gen")
    if isinstance(spec, kw.Keyword):
        resolved = get_spec(spec)
        if resolved is None:
            raise TypeError(f"cannot generate values for undefined spec {spec}")
        return _strategy_for_value(resolved)
    if isinstance(spec, _Nilable):
        return strategies.one_of(strategies.none(), _strategy_for_value(spec.spec))
    if isinstance(spec, _Or):
        return strategies.one_of(
            *(_strategy_for_value(child) for _tag, child in spec.branches)
        )
    if isinstance(spec, _Tuple):
        return strategies.tuples(*(_strategy_for_value(child) for child in spec.specs))
    if isinstance(spec, _CollOf):
        if spec.kind not in (None, list, tuple, vec.PersistentVector):
            raise TypeError(
                "cannot generate values for coll-of with an arbitrary :kind"
            )
        min_size = spec.count if spec.count is not None else spec.min_count or 0
        max_size = spec.count if spec.count is not None else spec.max_count or 8
        generated = strategies.lists(
            _strategy_for_value(spec.spec),
            min_size=min_size,
            max_size=max_size,
            unique=spec.distinct,
        )
        if spec.kind is tuple:
            return generated.map(tuple)
        if spec.kind is vec.PersistentVector:
            return generated.map(lambda values: vec.v(*values))
        return generated
    if isinstance(spec, _MapOf):
        return strategies.dictionaries(
            _strategy_for_value(spec.key_spec),
            _strategy_for_value(spec.value_spec),
            max_size=8,
        )
    if isinstance(spec, _Keys):
        required = {
            data_key: _strategy_for_registered_keyword(spec_key)
            for data_key, spec_key in spec.required
        }
        optional = {
            data_key: _strategy_for_registered_keyword(spec_key)
            for data_key, spec_key in spec.optional
        }
        return strategies.fixed_dictionaries(required, optional=optional)
    if isinstance(spec, IPersistentSet) or isinstance(spec, (set, frozenset)):
        values = tuple(spec)
        if not values:
            raise TypeError("cannot generate values from an empty set spec")
        return strategies.sampled_from(values)
    if spec is int:
        return strategies.integers()
    if spec is str:
        return strategies.text()
    if spec is bool:
        return strategies.booleans()
    if spec is float:
        return strategies.floats(allow_nan=False)
    if spec is bytes:
        return strategies.binary()
    if spec is type(None):
        return strategies.none()
    raise TypeError(f"cannot generate values for {spec!r}; wrap it with with-gen")


def _strategy_for_registered_keyword(key: kw.Keyword) -> Any:
    resolved = get_spec(key)
    if resolved is None:
        raise TypeError(f"cannot generate values for undefined spec {key}")
    return _strategy_for_value(resolved)


def _hypothesis_strategies() -> Any:
    try:
        from hypothesis import strategies
    except ImportError as exc:  # pragma: no cover - development dependency
        raise RuntimeError(
            "generated function checks require the optional Hypothesis dependency"
        ) from exc
    return strategies


def _resolve_strategy(generator: Any) -> Any:
    strategy = generator() if callable(generator) else generator
    if not hasattr(strategy, "example") or not hasattr(strategy, "map"):
        raise TypeError(
            "with-gen requires a Hypothesis strategy or zero-argument factory"
        )
    return strategy


def _flatten_generated_values(values: Iterable[Any]) -> tuple[Any, ...]:
    flattened: list[Any] = []
    for value in values:
        flattened.extend(value)
    return tuple(flattened)


def _merge_maps(values: Iterable[Any]) -> IPersistentMap:
    result: dict[Any, Any] = {}
    for value in values:
        if not _mapping(value):
            raise TypeError("merge specs must conform to maps")
        result.update(value)
    return lmap.map(result)


def _qualified_pairs(
    pairs: tuple[tuple[kw.Keyword, kw.Keyword], ...],
) -> tuple[kw.Keyword, ...]:
    return tuple(spec_key for data_key, spec_key in pairs if data_key == spec_key)


def _unqualified_pairs(
    pairs: tuple[tuple[kw.Keyword, kw.Keyword], ...],
) -> tuple[kw.Keyword, ...]:
    return tuple(spec_key for data_key, spec_key in pairs if data_key != spec_key)


def _keys_form(spec_: _Keys, *, qualified: bool) -> Any:
    name = (
        sym.symbol("keys", ns="clojure.spec.alpha") if qualified else sym.symbol("keys")
    )
    parts: list[Any] = [name]
    req = _qualified_pairs(spec_.required)
    req_un = _unqualified_pairs(spec_.required)
    opt = _qualified_pairs(spec_.optional)
    opt_un = _unqualified_pairs(spec_.optional)
    if req:
        parts.extend((kw.keyword("req"), vec.v(*req)))
    if req_un:
        parts.extend((kw.keyword("req-un"), vec.v(*req_un)))
    if opt:
        parts.extend((kw.keyword("opt"), vec.v(*opt)))
    if opt_un:
        parts.extend((kw.keyword("opt-un"), vec.v(*opt_un)))
    return llist.l(*parts)


# ``s/gen`` uses Basilisp's portable test.check implementation, rather than
# Hypothesis.  The latter remains the engine for spec.test/check because it
# gives Python tests excellent shrinking and diagnostics; keeping the two
# paths separate means requesting a normal Clojure generator never introduces
# an optional dependency.
def gen(spec: Any, overrides: Mapping[Any, Any] | None = None) -> Any:
    """Return a portable test.check generator for ``spec``.

    Values yielded by the returned generator are always filtered through the
    supplied spec.  This makes explicit generators and generator overrides a
    safe extension point, just as they are in Clojure's ``s/gen``.
    """
    impl = _test_check_impl()
    generated = _generator_for_value(spec, overrides or {}, (), frozenset())
    return impl.such_that(
        lambda value: valid(spec, value), generated, {"max-tries": 100}
    )


def exercise(
    spec: Any, n: int = 10, overrides: Mapping[Any, Any] | None = None
) -> vec.PersistentVector:
    """Generate ``n`` values for ``spec`` paired with their conformed values."""
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("exercise sample count must be a non-negative integer")
    impl = _test_check_impl()
    return vec.v(
        *(
            vec.v(value, conform(spec, value))
            for value in impl.sample(gen(spec, overrides), n)
        )
    )


def exercise_fn(
    target: Any, n: int = 10, function_spec: _FSpec | None = None
) -> vec.PersistentVector:
    """Apply a function to generated samples from its registered ``:args`` spec."""
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("exercise-fn sample count must be a non-negative integer")
    if isinstance(target, Var):
        function = target.root
        function_spec = function_spec or get_fspec(target)
    elif callable(target):
        function = target
    else:
        raise TypeError("exercise-fn expects a callable or a Basilisp Var")
    if not isinstance(function_spec, _FSpec) or function_spec.args is None:
        raise ValueError("No :args spec found, can't generate")
    impl = _test_check_impl()
    return vec.v(
        *(
            vec.v(args, function(*args))
            for args in impl.sample(gen(function_spec.args), n)
        )
    )


def _test_check_impl() -> Any:
    # This import is intentionally lazy: spec validation must not make the
    # property-testing implementation a startup dependency.
    from basilisp.test.check import _impl

    return _impl


def _generator_override(
    spec: Any, overrides: Mapping[Any, Any], path: tuple[Any, ...]
) -> Any | None:
    if not overrides:
        return None
    sentinel = object()
    candidate = overrides.get(spec, sentinel)
    if candidate is sentinel:
        candidate = overrides.get(vec.v(*path), sentinel)
    if candidate is sentinel:
        return None
    return _resolve_test_check_generator(candidate)


def _resolve_test_check_generator(source: Any) -> Any:
    impl = _test_check_impl()
    generator = source if impl.generator_q(source) else source()
    if not impl.generator_q(generator):
        raise TypeError(
            "s/gen overrides and with-gen must provide test.check generators"
        )
    return generator


def _recursive_reference_generator(
    spec: kw.Keyword,
    resolved: Any,
    overrides: Mapping[Any, Any],
    path: tuple[Any, ...],
    seen: frozenset[kw.Keyword],
) -> Any:
    impl = _test_check_impl()

    def build(size: int) -> Any:
        if size <= 1:
            return _base_generator_for_value(
                resolved, overrides, path, frozenset({spec})
            )
        return impl.resize(
            max(0, size // 2), _generator_for_value(resolved, overrides, path, seen)
        )

    return impl.sized(build)


def _maybe_deref(value: Any) -> Any:
    return value.deref() if isinstance(value, Var) else value


def _multispec_dispatch_value(spec: _MultiSpec, value: Any) -> Any:
    target = _maybe_deref(spec.dispatch)
    dispatch = getattr(target, "dispatch", None)
    if callable(dispatch):
        return dispatch(value)
    return target(value)


def _multispec_spec_for_value(spec: _MultiSpec, value: Any) -> tuple[Any, Any | None]:
    if spec.retag is None:
        selected = spec.dispatch(value)
        if not isinstance(selected, kw.Keyword):
            raise TypeError("multi-spec dispatch must return a keyword spec name")
        return selected, None

    target = _maybe_deref(spec.dispatch)
    dispatch_value = _multispec_dispatch_value(spec, value)
    selected_method = getattr(target, "get_method", lambda _key: None)(dispatch_value)
    if selected_method is None:
        raise TypeError("multi-spec multimethod has no method for dispatch value")
    return selected_method(value), dispatch_value


def _retag_multispec_value(retag: Any, value: Any, dispatch_value: Any) -> Any:
    if isinstance(retag, kw.Keyword):
        if value is None:
            return lmap.map({retag: dispatch_value})
        if hasattr(value, "assoc"):
            return value.assoc(retag, dispatch_value)
        if isinstance(value, Mapping):
            return lmap.map({**value, retag: dispatch_value})
        raise TypeError("multi-spec keyword retag requires an associative value")
    if callable(retag):
        return retag(value, dispatch_value)
    raise TypeError("multi-spec retag must be a keyword or callable")


def _multispec_method_generators(
    spec: _MultiSpec,
    overrides: Mapping[Any, Any],
    path: tuple[Any, ...],
    seen: frozenset[kw.Keyword],
    *,
    base: bool,
) -> tuple[Any, ...]:
    if spec.retag is None:
        raise TypeError(
            "cannot generate multi-spec values without an explicit multimethod retag"
        )
    target = _maybe_deref(spec.dispatch)
    methods = getattr(target, "methods", None)
    if methods is None:
        raise TypeError(
            "cannot generate multi-spec values without an enumerable multimethod"
        )

    generators = []
    for dispatch_value, method in methods.items():
        if invalid_q(dispatch_value):
            continue
        branch_spec = method(None)
        try:
            branch_generator = (
                _base_generator_for_value(
                    branch_spec, overrides, (*path, dispatch_value), seen
                )
                if base
                else _generator_for_value(
                    branch_spec, overrides, (*path, dispatch_value), seen
                )
            )
        except TypeError:
            continue
        generators.append(
            _test_check_impl().fmap(
                functools.partial(
                    _retag_multispec_value, spec.retag, dispatch_value=dispatch_value
                ),
                branch_generator,
            )
        )
    if not generators:
        raise TypeError("cannot generate multi-spec values with no generatable methods")
    return tuple(generators)


def _fspec_generator(
    spec: _FSpec,
    overrides: Mapping[Any, Any],
    path: tuple[Any, ...],
    seen: frozenset[kw.Keyword],
    *,
    base: bool,
) -> Any:
    if spec.args is None:
        raise TypeError("cannot generate function values for fspec without :args")
    impl = _test_check_impl()
    if spec.ret is None:
        ret_generator = impl.simple_type_printable
    else:
        ret_generator = (
            _base_generator_for_value(spec.ret, overrides, (*path, _CALL_RET), seen)
            if base
            else _generator_for_value(spec.ret, overrides, (*path, _CALL_RET), seen)
        )
        ret_generator = impl.such_that(
            lambda value: valid(spec.ret, value), ret_generator, {"max-tries": 100}
        )
    return impl.return_(
        _GeneratedFSpecFunction(spec.args, spec.ret, spec.fn, ret_generator)
    )


def _base_generator_for_value(
    spec: Any,
    overrides: Mapping[Any, Any],
    path: tuple[Any, ...],
    blocked: frozenset[kw.Keyword],
) -> Any:
    impl = _test_check_impl()
    overridden = _generator_override(spec, overrides, path)
    if overridden is not None:
        return overridden
    if isinstance(spec, _WithGen):
        return _resolve_test_check_generator(spec.generator)
    if isinstance(spec, _PredicateSpec):
        return _base_generator_for_value(spec.predicate, overrides, path, blocked)
    if isinstance(spec, _Nonconforming):
        return _base_generator_for_value(spec.spec, overrides, path, blocked)
    if isinstance(spec, _Conformer):
        raise TypeError("cannot generate values for conformer; wrap it with with-gen")
    if isinstance(spec, kw.Keyword):
        if spec in blocked:
            raise TypeError(
                "cannot generate recursively-defined specs without a nonrecursive branch"
            )
        resolved = get_spec(spec)
        if resolved is None:
            raise TypeError(f"cannot generate values for undefined spec {spec}")
        return _base_generator_for_value(
            resolved, overrides, (*path, spec), blocked | {spec}
        )
    if isinstance(spec, _And):
        for child in spec.specs:
            try:
                candidate = _base_generator_for_value(child, overrides, path, blocked)
                return impl.such_that(
                    lambda value: valid(spec, value), candidate, {"max-tries": 100}
                )
            except TypeError:
                continue
        raise TypeError("cannot generate values for s/and without a generatable child")
    if isinstance(spec, _Or):
        generators = []
        for tag, child in spec.branches:
            try:
                generators.append(
                    _base_generator_for_value(child, overrides, (*path, tag), blocked)
                )
            except TypeError:
                continue
        if generators:
            return impl.one_of(generators)
        raise TypeError(
            "cannot generate recursively-defined specs without a nonrecursive branch"
        )
    if isinstance(spec, _Nilable):
        try:
            child = _base_generator_for_value(spec.spec, overrides, path, blocked)
        except TypeError:
            return impl.return_(None)
        return impl.one_of((impl.return_(None), child))
    if isinstance(spec, _CollOf):
        try:
            child = _base_generator_for_value(spec.spec, overrides, path, blocked)
        except TypeError:
            if spec.count not in (None, 0) or (
                spec.min_count is not None and spec.min_count > 0
            ):
                raise
            return _collection_generator_for_kind(impl.return_(vec.EMPTY), spec.kind)
        lower = spec.count if spec.count is not None else spec.min_count
        upper = spec.count if spec.count is not None else min(spec.max_count or 0, 0)
        return _collection_generator_for_kind(
            impl.vector(child, lower, upper), spec.kind
        )
    if isinstance(spec, _MapOf):
        return impl.map_gen(
            _base_generator_for_value(spec.key_spec, overrides, path, blocked),
            _base_generator_for_value(spec.value_spec, overrides, path, blocked),
        )
    if isinstance(spec, _Keys):
        return _base_keys_generator(spec, overrides, path, blocked)
    if isinstance(spec, _KeysStar):
        return impl.fmap(
            _map_to_key_value_vector,
            _base_keys_generator(spec.map_spec, overrides, path, blocked),
        )
    if isinstance(spec, _Tuple):
        return impl.tuple_gen(
            *(
                _base_generator_for_value(child, overrides, (*path, index), blocked)
                for index, child in enumerate(spec.specs)
            )
        )
    if isinstance(spec, _Regex):
        return _base_regex_generator(spec, overrides, path, blocked)
    if isinstance(spec, _FSpec):
        return _fspec_generator(spec, overrides, path, blocked, base=True)
    if isinstance(spec, _MultiSpec):
        return impl.one_of(
            _multispec_method_generators(spec, overrides, path, blocked, base=True)
        )
    return _generator_for_predicate(spec)


def _base_keys_generator(
    spec: _Keys,
    overrides: Mapping[Any, Any],
    path: tuple[Any, ...],
    blocked: frozenset[kw.Keyword],
) -> Any:
    impl = _test_check_impl()
    required = tuple(
        (
            data_key,
            _base_generator_for_value(spec_key, overrides, (*path, data_key), blocked),
        )
        for data_key, spec_key in spec.required
    )
    optional = []
    for data_key, spec_key in spec.optional:
        try:
            optional.append(
                (
                    data_key,
                    _base_generator_for_value(
                        spec_key, overrides, (*path, data_key), blocked
                    ),
                )
            )
        except TypeError:
            continue
    parts = [generator for _key, generator in required]
    parts.extend(
        impl.tuple_gen(impl.boolean, generator) for _key, generator in optional
    )
    if not parts:
        return impl.return_(lmap.map({}))

    def build(values: Sequence[Any]) -> IPersistentMap:
        result = {
            key: values[index] for index, (key, _generator) in enumerate(required)
        }
        offset = len(required)
        for index, (key, _generator) in enumerate(optional):
            present, value = values[offset + index]
            if present:
                result[key] = value
        return lmap.map(result)

    return impl.fmap(build, impl.tuple_gen(*parts))


def _base_regex_generator(
    spec: Any,
    overrides: Mapping[Any, Any],
    path: tuple[Any, ...],
    blocked: frozenset[kw.Keyword],
) -> Any:
    impl = _test_check_impl()
    if isinstance(spec, _WithGen):
        return _resolve_test_check_generator(spec.generator)
    if isinstance(spec, kw.Keyword):
        return _base_generator_for_value(spec, overrides, path, blocked)
    if isinstance(spec, _Cat):
        return impl.fmap(
            lambda values: vec.v(*_flatten_generated_values(values)),
            impl.tuple_gen(
                *(
                    _base_regex_generator(child, overrides, (*path, tag), blocked)
                    for tag, child in spec.branches
                )
            ),
        )
    if isinstance(spec, _Alt):
        generators = []
        for tag, child in spec.branches:
            try:
                generators.append(
                    _base_regex_generator(child, overrides, (*path, tag), blocked)
                )
            except TypeError:
                continue
        if generators:
            return impl.one_of(generators)
        raise TypeError(
            "cannot generate recursively-defined regex specs without a nonrecursive branch"
        )
    if isinstance(spec, _Repeat):
        if spec.minimum == 0:
            return impl.return_(vec.EMPTY)
        generated = _base_regex_generator(spec.spec, overrides, path, blocked)
        return impl.fmap(
            lambda values: vec.v(*_flatten_generated_values(values)),
            impl.vector(generated, spec.minimum, spec.minimum),
        )
    if isinstance(spec, _Maybe):
        return impl.return_(vec.EMPTY)
    if isinstance(spec, _KeysStar):
        return impl.fmap(
            _map_to_key_value_vector,
            _base_keys_generator(spec.map_spec, overrides, path, blocked),
        )
    if isinstance(spec, _Amp):
        generated = _base_regex_generator(spec.spec, overrides, path, blocked)
        return impl.such_that(
            lambda value: valid(spec, value), generated, {"max-tries": 100}
        )
    return impl.fmap(
        lambda value: vec.v(value),
        _base_generator_for_value(spec, overrides, path, blocked),
    )


def _generator_for_value(
    spec: Any,
    overrides: Mapping[Any, Any],
    path: tuple[Any, ...],
    seen: frozenset[kw.Keyword],
) -> Any:
    impl = _test_check_impl()
    overridden = _generator_override(spec, overrides, path)
    if overridden is not None:
        return overridden
    if isinstance(spec, _WithGen):
        return _resolve_test_check_generator(spec.generator)
    if isinstance(spec, _PredicateSpec):
        return _generator_for_value(spec.predicate, overrides, path, seen)
    if isinstance(spec, _Nonconforming):
        return _generator_for_value(spec.spec, overrides, path, seen)
    if isinstance(spec, _Merge):
        return impl.fmap(
            _merge_maps,
            impl.tuple_gen(
                *(
                    _generator_for_value(child, overrides, path, seen)
                    for child in spec.specs
                )
            ),
        )
    if isinstance(spec, _Conformer):
        raise TypeError("cannot generate values for conformer; wrap it with with-gen")
    if isinstance(spec, kw.Keyword):
        resolved = get_spec(spec)
        if resolved is None:
            raise TypeError(f"cannot generate values for undefined spec {spec}")
        if spec in seen:
            return _recursive_reference_generator(
                spec, resolved, overrides, (*path, spec), seen
            )
        return _generator_for_value(resolved, overrides, (*path, spec), seen | {spec})
    if isinstance(spec, _And):
        errors: list[TypeError] = []
        for child in spec.specs:
            try:
                candidate = _generator_for_value(child, overrides, path, seen)
                return impl.such_that(
                    lambda value: valid(spec, value), candidate, {"max-tries": 100}
                )
            except TypeError as exc:
                errors.append(exc)
        raise TypeError(
            "cannot generate values for s/and without a generatable child"
        ) from (errors[-1] if errors else None)
    if isinstance(spec, _Or):
        return impl.one_of(
            _generator_for_value(child, overrides, (*path, tag), seen)
            for tag, child in spec.branches
        )
    if isinstance(spec, _Nilable):
        return impl.one_of(
            (impl.return_(None), _generator_for_value(spec.spec, overrides, path, seen))
        )
    if isinstance(spec, _CollOf):
        child = _generator_for_value(spec.spec, overrides, path, seen)
        lower = spec.count if spec.count is not None else spec.min_count
        upper = spec.count if spec.count is not None else spec.max_count
        if spec.distinct:
            options: dict[str, Any] = {}
            if lower is not None:
                options["min-elements"] = lower
            if upper is not None:
                options["max-elements"] = upper
            generated = impl.vector_distinct(child, options)
        else:
            generated = impl.vector(child, lower, upper)
        return _collection_generator_for_kind(generated, spec.kind)
    if isinstance(spec, _MapOf):
        return impl.map_gen(
            _generator_for_value(spec.key_spec, overrides, path, seen),
            _generator_for_value(spec.value_spec, overrides, path, seen),
        )
    if isinstance(spec, _Keys):
        return _keys_generator(spec, overrides, path, seen)
    if isinstance(spec, _KeysStar):
        return impl.fmap(
            _map_to_key_value_vector,
            _keys_generator(spec.map_spec, overrides, path, seen),
        )
    if isinstance(spec, _Tuple):
        return impl.tuple_gen(
            *(
                _generator_for_value(child, overrides, (*path, index), seen)
                for index, child in enumerate(spec.specs)
            )
        )
    if isinstance(spec, _Regex):
        return _regex_generator(spec, overrides, path, seen)
    if isinstance(spec, _FSpec):
        return _fspec_generator(spec, overrides, path, seen, base=False)
    if isinstance(spec, _MultiSpec):
        return impl.one_of(
            _multispec_method_generators(spec, overrides, path, seen, base=False)
        )
    return _generator_for_predicate(spec)


def _collection_generator_for_kind(generator: Any, kind: Any | None) -> Any:
    impl = _test_check_impl()
    if kind in (None, vec.PersistentVector) or _callable_name(kind) == "vector__Q__":
        return generator
    if kind is list or _callable_name(kind) == "list__Q__":
        return impl.fmap(llist.list, generator)
    if kind is tuple or _callable_name(kind) == "tuple__Q__":
        return impl.fmap(tuple, generator)
    raise TypeError("cannot generate values for coll-of with an arbitrary :kind")


def _keys_generator(
    spec: _Keys,
    overrides: Mapping[Any, Any],
    path: tuple[Any, ...],
    seen: frozenset[kw.Keyword],
) -> Any:
    impl = _test_check_impl()
    required = tuple(
        (
            data_key,
            _generator_for_value(spec_key, overrides, (*path, data_key), seen),
        )
        for data_key, spec_key in spec.required
    )
    optional = tuple(
        (
            data_key,
            _generator_for_value(spec_key, overrides, (*path, data_key), seen),
        )
        for data_key, spec_key in spec.optional
    )
    parts = [generator for _key, generator in required]
    parts.extend(
        impl.tuple_gen(impl.boolean, generator) for _key, generator in optional
    )
    if not parts:
        return impl.return_(lmap.map({}))

    def build(values: Sequence[Any]) -> IPersistentMap:
        result = {
            key: values[index] for index, (key, _generator) in enumerate(required)
        }
        offset = len(required)
        for index, (key, _generator) in enumerate(optional):
            present, value = values[offset + index]
            if present:
                result[key] = value
        return lmap.map(result)

    return impl.fmap(build, impl.tuple_gen(*parts))


def _map_to_key_value_vector(value: Mapping[Any, Any]) -> vec.PersistentVector:
    items: list[Any] = []
    for key, item in value.items():
        items.extend((key, item))
    return vec.v(*items)


def _regex_generator(
    spec: Any,
    overrides: Mapping[Any, Any],
    path: tuple[Any, ...],
    seen: frozenset[kw.Keyword],
) -> Any:
    impl = _test_check_impl()
    overridden = _generator_override(spec, overrides, path)
    if overridden is not None:
        return overridden
    if isinstance(spec, _WithGen):
        return _resolve_test_check_generator(spec.generator)
    if isinstance(spec, kw.Keyword):
        resolved = get_spec(spec)
        if resolved is None:
            raise TypeError(f"cannot generate values for undefined spec {spec}")
        return _regex_generator(resolved, overrides, (*path, spec), seen | {spec})
    if isinstance(spec, _Cat):
        return impl.fmap(
            lambda values: vec.v(*_flatten_generated_values(values)),
            impl.tuple_gen(
                *(
                    _regex_generator(child, overrides, (*path, tag), seen)
                    for tag, child in spec.branches
                )
            ),
        )
    if isinstance(spec, _Alt):
        return impl.one_of(
            _regex_generator(child, overrides, (*path, tag), seen)
            for tag, child in spec.branches
        )
    if isinstance(spec, _Repeat):
        repeated = impl.vector(
            _regex_generator(spec.spec, overrides, path, seen), spec.minimum
        )
        return impl.fmap(
            lambda values: vec.v(*_flatten_generated_values(values)), repeated
        )
    if isinstance(spec, _Maybe):
        return impl.one_of(
            (
                impl.return_(vec.EMPTY),
                _regex_generator(spec.spec, overrides, path, seen),
            )
        )
    if isinstance(spec, _KeysStar):
        return impl.fmap(
            _map_to_key_value_vector,
            _keys_generator(spec.map_spec, overrides, path, seen),
        )
    if isinstance(spec, _Amp):
        generated = _regex_generator(spec.spec, overrides, path, seen)
        return impl.such_that(
            lambda value: valid(spec, value), generated, {"max-tries": 100}
        )
    return impl.fmap(
        lambda value: vec.v(value), _generator_for_value(spec, overrides, path, seen)
    )


def _callable_name(value: Any) -> str | None:
    return getattr(value, "__name__", None)


def _generator_for_predicate(spec: Any) -> Any:
    impl = _test_check_impl()
    if isinstance(spec, IPersistentSet) or isinstance(spec, (set, frozenset)):
        if not spec:
            raise TypeError("cannot generate values from an empty set spec")
        return impl.elements(spec)
    if spec is int:
        return impl.large_integer
    if spec is str:
        return impl.string_alphanumeric
    if spec is bool:
        return impl.boolean
    if spec is float:
        return impl.double
    if spec is bytes:
        return impl.bytes
    if spec is type(None):
        return impl.return_(None)

    name = _callable_name(spec)
    simple: dict[str, Any] = {
        "any__Q__": impl.any,
        "boolean__Q__": impl.boolean,
        "bytes__Q__": impl.bytes,
        "char__Q__": impl.char,
        "double__Q__": impl.double,
        "float__Q__": impl.double,
        "int__Q__": impl.large_integer,
        "integer__Q__": impl.large_integer,
        "keyword__Q__": impl.keyword_ns,
        "list__Q__": impl.list_gen(impl.simple_type_printable),
        "map__Q__": impl.map_gen(
            impl.simple_type_printable, impl.simple_type_printable
        ),
        "number__Q__": impl.one_of((impl.large_integer, impl.double)),
        "ratio__Q__": impl.ratio,
        "seq__Q__": impl.list_gen(impl.simple_type_printable),
        "set__Q__": impl.set_gen(impl.simple_type_printable),
        "string__Q__": impl.string_alphanumeric,
        "symbol__Q__": impl.symbol_ns,
        "uuid__Q__": impl.uuid,
        "vector__Q__": impl.vector(impl.simple_type_printable),
    }
    if name in simple:
        return simple[name]
    if name == "some__Q__":
        return impl.such_that(bool, impl.any_printable, {"max-tries": 100})
    if name == "nil__Q__":
        return impl.return_(None)
    if name == "true__Q__":
        return impl.return_(True)
    if name == "false__Q__":
        return impl.return_(False)
    if name == "zero__Q__":
        return impl.return_(0)
    if name == "pos_int__Q__":
        return impl.large_integer_star({"min": 1})
    if name == "neg_int__Q__":
        return impl.large_integer_star({"max": -1})
    if name == "nat_int__Q__":
        return impl.large_integer_star({"min": 0})
    if name in {"ident__Q__", "qualified_ident__Q__"}:
        return impl.one_of((impl.keyword_ns, impl.symbol_ns))
    if name == "simple_ident__Q__":
        return impl.one_of((impl.keyword, impl.symbol))
    if name == "simple_keyword__Q__":
        return impl.keyword
    if name == "qualified_keyword__Q__":
        return impl.keyword_ns
    if name == "simple_symbol__Q__":
        return impl.symbol
    if name == "qualified_symbol__Q__":
        return impl.symbol_ns
    if name == "seqable__Q__":
        return impl.one_of(
            (
                impl.return_(None),
                impl.list_gen(impl.simple_type_printable),
                impl.vector(impl.simple_type_printable),
                impl.map_gen(impl.simple_type_printable, impl.simple_type_printable),
                impl.set_gen(impl.simple_type_printable),
                impl.string_alphanumeric,
            )
        )
    if name == "indexed__Q__":
        return impl.vector(impl.simple_type_printable)
    if name == "associative__Q__":
        return impl.one_of(
            (
                impl.vector(impl.simple_type_printable),
                impl.map_gen(impl.simple_type_printable, impl.simple_type_printable),
            )
        )
    if name == "sequential__Q__":
        return impl.one_of(
            (
                impl.vector(impl.simple_type_printable),
                impl.list_gen(impl.simple_type_printable),
            )
        )
    if name == "coll__Q__":
        return impl.one_of(
            (
                impl.vector(impl.simple_type_printable),
                impl.list_gen(impl.simple_type_printable),
                impl.map_gen(impl.simple_type_printable, impl.simple_type_printable),
                impl.set_gen(impl.simple_type_printable),
            )
        )
    if name == "rational__Q__":
        return impl.one_of((impl.large_integer, impl.ratio))
    if name == "decimal__Q__":
        import decimal

        return impl.fmap(
            lambda value: decimal.Decimal(str(value)),
            impl.double_star({"infinite?": False, "NaN?": False}),
        )
    if name == "inst__Q__":
        import datetime

        return impl.return_(datetime.datetime(1970, 1, 1))
    if name in {"uri__Q__", "uri_qmark"}:
        import urllib.parse

        return impl.fmap(
            lambda value: urllib.parse.urlparse(f"https://{value}.example"), impl.uuid
        )
    raise TypeError(f"cannot generate values for {spec!r}; wrap it with with-gen")


def _validate_instrument_target(target: Var) -> None:
    if not isinstance(target, Var):
        raise TypeError("instrument targets must be Basilisp Vars")
    if target.dynamic:
        raise TypeError("cannot instrument dynamic Vars")
    if target in _INSTRUMENTED:
        return

    function_spec = _FUNCTION_SPECS.get(target)
    if function_spec is None:
        raise ValueError("cannot instrument a Var without an fdef")

    original = target.root
    if not callable(original):
        raise TypeError("can only instrument Vars with callable roots")


def _instrument(target: Var) -> None:
    if target in _INSTRUMENTED:
        return

    original = target.root

    module_name = _module_binding_name(target)
    module_value = getattr(target.ns.module, module_name, _MISSING)

    @functools.wraps(original)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        return _validate_call(target, original, args, kwargs)

    target.bind_root(wrapped)
    setattr(target.ns.module, module_name, wrapped)
    _INSTRUMENTED[target] = _Instrumented(
        original=original,
        module_name=module_name,
        module_value=module_value,
        wrapper=wrapped,
    )


def _unstrument(target: Var) -> None:
    if not isinstance(target, Var):
        raise TypeError("unstrument targets must be Basilisp Vars")
    instrumented = _INSTRUMENTED.pop(target, None)
    if instrumented is None:
        return

    if target.root is instrumented.wrapper:
        target.bind_root(instrumented.original)
    if (
        getattr(target.ns.module, instrumented.module_name, _MISSING)
        is instrumented.wrapper
    ):
        if instrumented.module_value is _MISSING:
            delattr(target.ns.module, instrumented.module_name)
        else:
            setattr(
                target.ns.module, instrumented.module_name, instrumented.module_value
            )


def _module_binding_name(target: Var) -> str:
    name = target.name.name
    safe_name = munge(name)
    if safe_name in vars(target.ns.module):
        return safe_name
    builtin_safe_name = munge(name, allow_builtins=True)
    if builtin_safe_name in vars(target.ns.module):
        return builtin_safe_name
    return safe_name


def _validate_call(
    target: Var,
    original: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    function_spec = _FUNCTION_SPECS.get(target)
    if function_spec is None:
        return original(*args, **kwargs)

    call_args = vec.v(*args)
    conformed_args = call_args
    if function_spec.args is not None:
        if kwargs:
            raise ExceptionInfo(
                "Cannot validate keyword arguments against an fdef :args spec",
                lmap.map(
                    {
                        _CALL_TARGET: _var_symbol(target),
                        _CALL_ARGS: call_args,
                        _CALL_KEYWORD_ARGS: lmap.map(kwargs),
                    }
                ),
            )
        conformed_args = _validate_function_value(
            target, ":args", function_spec.args, call_args
        )

    result = original(*args, **kwargs)
    if function_spec.ret is not None:
        _validate_function_value(target, ":ret", function_spec.ret, result)
    if function_spec.fn is not None:
        _validate_function_value(
            target,
            ":fn",
            function_spec.fn,
            lmap.map({_CALL_ARGS: conformed_args, _CALL_RET: result}),
        )
    return result


def _validate_function_value(target: Var, role: str, contract: Any, value: Any) -> Any:
    conformed = conform(contract, value)
    if conformed is not INVALID:
        return conformed
    details = explain_data(contract, value)
    assert details is not None
    raise ExceptionInfo(
        f"Call to {_var_symbol(target)} did not conform to its {role} spec",
        details.assoc(_CALL_TARGET, _var_symbol(target)),
    )


def _var_symbol(target: Var) -> str:
    return f"{target.ns.name}/{target.name.name}"


def valid(spec: Any, value: Any) -> bool:
    return _conform(spec, value, (), (), (), None) is not INVALID


def conform(spec: Any, value: Any) -> Any:
    return _conform(spec, value, (), (), (), None)


def unform(spec: Any, value: Any) -> Any:
    if isinstance(spec, _Regex):
        return vec.v(*_unform_regex(spec, value))
    if isinstance(spec, _WithGen):
        return unform(spec.spec, value)
    if isinstance(spec, _PredicateSpec):
        return unform(spec.predicate, value)
    if isinstance(spec, _Conformer):
        return value if spec.unformer is None else spec.unformer(value)
    if isinstance(spec, _Nonconforming):
        return value
    if isinstance(spec, _Merge):
        return _merge_maps(unform(child, value) for child in reversed(spec.specs))
    if isinstance(spec, kw.Keyword):
        resolved = get_spec(spec)
        return value if resolved is None else unform(resolved, value)
    if isinstance(spec, _Or) and _sequence(value) and len(value) == 2:
        tag, conformed = value
        for branch_tag, branch_spec in spec.branches:
            if tag == branch_tag:
                return unform(branch_spec, conformed)
    return value


def explain_data(spec: Any, value: Any) -> IPersistentMap | None:
    problems: list[IPersistentMap] = []
    if _conform(spec, value, (), (), (), problems) is not INVALID:
        return None
    return lmap.map({_PROBLEMS: vec.v(*problems)})


def form(spec_: Any) -> Any:
    """Return a data representation of a portable spec descriptor."""
    if isinstance(spec_, _WithGen):
        return form(spec_.spec)
    if isinstance(spec_, _PredicateSpec):
        return form(spec_.predicate)
    if isinstance(spec_, _Conformer):
        values = [sym.symbol("conformer"), spec_.conformer]
        if spec_.unformer is not None:
            values.append(spec_.unformer)
        return llist.l(*values)
    if isinstance(spec_, _Nonconforming):
        return llist.l(sym.symbol("nonconforming"), form(spec_.spec))
    if isinstance(spec_, _Merge):
        return llist.l(sym.symbol("merge"), *(form(child) for child in spec_.specs))
    if isinstance(spec_, _And):
        return llist.l(sym.symbol("and"), *(form(child) for child in spec_.specs))
    if isinstance(spec_, _Or):
        return llist.l(
            sym.symbol("or"),
            *(item for tag, child in spec_.branches for item in (tag, form(child))),
        )
    if isinstance(spec_, _Nilable):
        return llist.l(sym.symbol("nilable"), form(spec_.spec))
    if isinstance(spec_, _CollOf):
        return llist.l(sym.symbol("coll-of"), form(spec_.spec))
    if isinstance(spec_, _MapOf):
        return llist.l(
            sym.symbol("map-of"), form(spec_.key_spec), form(spec_.value_spec)
        )
    if isinstance(spec_, _Keys):
        return _keys_form(spec_, qualified=True)
    if isinstance(spec_, _Tuple):
        return llist.l(sym.symbol("tuple"), *(form(child) for child in spec_.specs))
    return spec_


def describe(spec_: Any) -> Any:
    """Return a compact data description of a portable spec descriptor."""
    if isinstance(spec_, _Keys):
        return _keys_form(spec_, qualified=False)
    return form(spec_)


def explain_printer(data: IPersistentMap | None, writer: Any = None) -> None:
    """Print a concise, host-portable explanation for ``explain-data`` output."""
    stream = writer if writer is not None else None

    def emit(message: str) -> None:
        if stream is None:
            print(message)
        else:
            stream.write(message + "\n")

    if data is None:
        emit("Success!")
        return
    for problem in data.val_at(_PROBLEMS, vec.EMPTY):
        value = problem.val_at(_VAL)
        predicate = problem.val_at(_PRED)
        message = f"{value!r} - failed: {predicate!r}"
        location = problem.val_at(_IN, vec.EMPTY)
        path = problem.val_at(_PATH, vec.EMPTY)
        via = problem.val_at(_VIA, vec.EMPTY)
        if len(location):
            message += f" in: {location!r}"
        if len(path):
            message += f" at: {path!r}"
        if len(via):
            message += f" spec: {via[len(via) - 1]!r}"
        emit(message)


def explain_out(data: IPersistentMap | None) -> None:
    explain_printer(data)


def explain(spec_: Any, value: Any) -> None:
    explain_out(explain_data(spec_, value))


def explain_str(spec_: Any, value: Any) -> str:
    output = io.StringIO()
    explain_printer(explain_data(spec_, value), output)
    return output.getvalue()


def and_(*specs: Any) -> _And:
    return _And(specs)


def or_(*tagged_specs: Any) -> _Or:
    if len(tagged_specs) % 2:
        raise ValueError("or requires tagged spec pairs")
    branches = []
    for tag, spec in zip(tagged_specs[::2], tagged_specs[1::2]):
        if not isinstance(tag, kw.Keyword):
            raise TypeError("or tags must be keywords")
        branches.append((tag, spec))
    return _Or(tuple(branches))


def nilable(spec: Any) -> _Nilable:
    return _Nilable(spec)


def coll_of(
    spec: Any,
    *,
    kind: Any | None = None,
    count: int | None = None,
    min_count: int | None = None,
    max_count: int | None = None,
    distinct: bool = False,
) -> _CollOf:
    return _CollOf(spec, kind, count, min_count, max_count, distinct)


def map_of(key_spec: Any, value_spec: Any) -> _MapOf:
    return _MapOf(key_spec, value_spec)


def _as_keyword(value: Any, label: str) -> kw.Keyword:
    if not isinstance(value, kw.Keyword):
        raise TypeError(f"{label} entries must be keywords")
    return value


def _unqualified_key(value: kw.Keyword) -> kw.Keyword:
    return kw.keyword(value.name)


def _key_specs(
    values: Iterable[kw.Keyword], *, unqualified: bool = False
) -> tuple[tuple[kw.Keyword, kw.Keyword], ...]:
    pairs: list[tuple[kw.Keyword, kw.Keyword]] = []
    for value in values:
        spec_key = _as_keyword(value, "keys")
        data_key = _unqualified_key(spec_key) if unqualified else spec_key
        pairs.append((data_key, spec_key))
    return tuple(pairs)


def keys(
    required: Iterable[kw.Keyword] = (),
    optional: Iterable[kw.Keyword] = (),
    required_unqualified: Iterable[kw.Keyword] = (),
    optional_unqualified: Iterable[kw.Keyword] = (),
) -> _Keys:
    return _Keys(
        (
            *_key_specs(required),
            *_key_specs(required_unqualified, unqualified=True),
        ),
        (
            *_key_specs(optional),
            *_key_specs(optional_unqualified, unqualified=True),
        ),
    )


def keys_star(
    required: Iterable[kw.Keyword] = (),
    optional: Iterable[kw.Keyword] = (),
    required_unqualified: Iterable[kw.Keyword] = (),
    optional_unqualified: Iterable[kw.Keyword] = (),
) -> _KeysStar:
    return _KeysStar(
        keys(required, optional, required_unqualified, optional_unqualified)
    )


def tuple_(*specs: Any) -> _Tuple:
    return _Tuple(specs)


def multi_spec(dispatch: Callable[[Any], Any], retag: Any | None = None) -> _MultiSpec:
    return _MultiSpec(dispatch, retag)


def cat(*tagged_specs: Any) -> _Cat:
    return _Cat(_tagged_specs("cat", tagged_specs))


def alt(*tagged_specs: Any) -> _Alt:
    return _Alt(_tagged_specs("alt", tagged_specs))


def star(spec: Any) -> _Repeat:
    return _Repeat(spec, 0)


def plus(spec: Any) -> _Repeat:
    return _Repeat(spec, 1)


def maybe(spec: Any) -> _Maybe:
    return _Maybe(spec)


def amp(spec: Any, *predicates: Any) -> _Amp:
    if not predicates:
        raise ValueError("& requires at least one predicate")
    return _Amp(spec, predicates)


def _conform(
    spec: Any,
    value: Any,
    path: tuple[Any, ...],
    via: tuple[kw.Keyword, ...],
    location: tuple[Any, ...],
    problems: list[IPersistentMap] | None,
) -> Any:
    if isinstance(spec, _Regex):
        return _conform_regex(spec, value, path, via, location, problems)
    if isinstance(spec, _FSpec):
        return (
            value
            if callable(value)
            else _invalid(spec, value, path, via, location, problems)
        )
    if isinstance(spec, _WithGen):
        return _conform(spec.spec, value, path, via, location, problems)
    if isinstance(spec, _PredicateSpec):
        return _conform(spec.predicate, value, path, via, location, problems)
    if isinstance(spec, _Conformer):
        try:
            conformed = spec.conformer(value)
        except BaseException:
            conformed = INVALID
        return (
            conformed
            if conformed is not INVALID
            else _invalid(spec, value, path, via, location, problems)
        )
    if isinstance(spec, _Nonconforming):
        conformed = _conform(spec.spec, value, path, via, location, problems)
        return INVALID if conformed is INVALID else value
    if isinstance(spec, _Merge):
        conformed: list[Any] = []
        for child in spec.specs:
            result = _conform(child, value, path, via, location, problems)
            if result is INVALID:
                return INVALID
            if not _mapping(result):
                return _invalid(spec, value, path, via, location, problems)
            conformed.append(result)
        return _merge_maps(conformed)
    if isinstance(spec, kw.Keyword):
        resolved = get_spec(spec)
        if resolved is None:
            return _invalid(spec, value, path, via, location, problems)
        return _conform(resolved, value, path, (*via, spec), location, problems)
    if isinstance(spec, _And):
        conformed = value
        for child in spec.specs:
            conformed = _conform(child, conformed, path, via, location, problems)
            if conformed is INVALID:
                return INVALID
        return conformed
    if isinstance(spec, _Or):
        all_problems: list[IPersistentMap] = []
        for tag, child in spec.branches:
            conformed = _conform(child, value, (*path, tag), via, location, None)
            if conformed is not INVALID:
                return vec.v(tag, conformed)
            if problems is not None:
                _conform(child, value, (*path, tag), via, location, all_problems)
        if problems is not None:
            problems.extend(all_problems)
        return INVALID
    if isinstance(spec, _Nilable):
        return (
            value
            if value is None
            else _conform(spec.spec, value, path, via, location, problems)
        )
    if isinstance(spec, _CollOf):
        return _conform_coll_of(spec, value, path, via, location, problems)
    if isinstance(spec, _MapOf):
        return _conform_map_of(spec, value, path, via, location, problems)
    if isinstance(spec, _Keys):
        return _conform_keys(spec, value, path, via, location, problems)
    if isinstance(spec, _Tuple):
        return _conform_tuple(spec, value, path, via, location, problems)
    if isinstance(spec, _MultiSpec):
        try:
            selected, dispatch_value = _multispec_spec_for_value(spec, value)
        except BaseException:
            return _invalid(spec.dispatch, value, path, via, location, problems)
        child_path = path if dispatch_value is None else (*path, dispatch_value)
        return _conform(selected, value, child_path, via, location, problems)
    if isinstance(spec, type):
        return (
            value
            if isinstance(value, spec)
            else _invalid(spec, value, path, via, location, problems)
        )
    if callable(spec):
        try:
            matches = bool(spec(value))
        except BaseException:
            matches = False
        return (
            value if matches else _invalid(spec, value, path, via, location, problems)
        )
    if isinstance(spec, IPersistentSet) or isinstance(spec, (set, frozenset)):
        return (
            value
            if value in spec
            else _invalid(spec, value, path, via, location, problems)
        )
    raise TypeError(f"unsupported spec: {spec!r}")


def _conform_coll_of(spec, value, path, via, location, problems):
    if not _sequence(value) or (
        spec.kind is not None and not _matches(spec.kind, value)
    ):
        return _invalid(
            spec.kind or "sequential?", value, path, via, location, problems
        )
    if (
        spec.count is not None
        and len(value) != spec.count
        or spec.min_count is not None
        and len(value) < spec.min_count
        or spec.max_count is not None
        and len(value) > spec.max_count
        or spec.distinct
        and len(set(value)) != len(value)
    ):
        return _invalid(spec, value, path, via, location, problems)
    for index, item in enumerate(value):
        if (
            _conform(spec.spec, item, path, via, (*location, index), problems)
            is INVALID
        ):
            return INVALID
    return value


def _conform_map_of(spec, value, path, via, location, problems):
    if not _mapping(value):
        return _invalid("map?", value, path, via, location, problems)
    for key, item in value.items():
        if (
            _conform(spec.key_spec, key, path, via, (*location, key), problems)
            is INVALID
        ):
            return INVALID
        if (
            _conform(spec.value_spec, item, path, via, (*location, key), problems)
            is INVALID
        ):
            return INVALID
    return value


def _conform_keys(spec, value, path, via, location, problems):
    if not _mapping(value):
        return _invalid("map?", value, path, via, location, problems)
    for data_key, _spec_key in spec.required:
        if data_key not in value:
            return _invalid(data_key, value, path, via, location, problems)
    for data_key, spec_key in (*spec.required, *spec.optional):
        if (
            data_key in value
            and _conform(
                spec_key,
                value[data_key],
                (*path, data_key),
                via,
                (*location, data_key),
                problems,
            )
            is INVALID
        ):
            return INVALID
    return value


def _conform_tuple(spec, value, path, via, location, problems):
    if not _sequence(value) or len(value) != len(spec.specs):
        return _invalid(spec, value, path, via, location, problems)
    for index, (child, item) in enumerate(zip(spec.specs, value)):
        if (
            _conform(child, item, (*path, index), via, (*location, index), problems)
            is INVALID
        ):
            return INVALID
    return value


def _conform_regex(spec, value, path, via, location, problems):
    if not _regex_sequence(value):
        return _invalid(spec, value, path, via, location, problems)
    values = tuple(value)
    for conformed, position in _match_regex_all(
        spec, values, 0, path, via, location, problems
    ):
        if position == len(values):
            return conformed
    return _invalid(spec, value, path, via, location, problems)


def _match_regex(spec, values, position, path, via, location, problems):
    for matched in _match_regex_all(
        spec, values, position, path, via, location, problems
    ):
        return matched
    return None


def _match_regex_all(spec, values, position, path, via, location, problems):
    if isinstance(spec, _Cat):
        yield from _match_cat(spec, values, position, path, via, location, problems)
        return
    if isinstance(spec, _KeysStar):
        yield from _match_keys_star(
            spec, values, position, path, via, location, problems
        )
        return
    if isinstance(spec, _Alt):
        for tag, child in spec.branches:
            matched = _match_regex(child, values, position, path, via, location, None)
            if matched is not None:
                conformed, next_position = matched
                yield vec.v(tag, conformed), next_position
                return
        if problems is not None:
            for _tag, child in spec.branches:
                _match_regex(child, values, position, path, via, location, problems)
        if position >= len(values):
            _invalid(spec, None, path, via, (*location, position), problems)
        return
    if isinstance(spec, _Repeat):
        matches = []
        while True:
            matched = _match_regex(
                spec.spec, values, position, path, via, location, None
            )
            if matched is None:
                break
            conformed, next_position = matched
            if next_position == position:
                raise ValueError("a repeated regex spec must consume an input value")
            matches.append(conformed)
            position = next_position
        if len(matches) < spec.minimum:
            if problems is not None:
                _match_regex(spec.spec, values, position, path, via, location, problems)
            return
        yield vec.v(*matches), position
        return
    if isinstance(spec, _Maybe):
        matched = _match_regex(spec.spec, values, position, path, via, location, None)
        yield (None, position) if matched is None else matched
        return
    if isinstance(spec, _Amp):
        matched = _match_regex(
            spec.spec, values, position, path, via, location, problems
        )
        if matched is None:
            return
        conformed, next_position = matched
        for predicate in spec.predicates:
            conformed = _conform(
                predicate, conformed, path, via, (*location, position), problems
            )
            if conformed is INVALID:
                return
        yield conformed, next_position
        return
    if position >= len(values):
        _invalid(spec, None, path, via, (*location, position), problems)
        return
    conformed = _conform(
        spec, values[position], path, via, (*location, position), problems
    )
    if conformed is INVALID:
        return
    yield conformed, position + 1


def _match_cat(spec, values, position, path, via, location, problems):
    branches = spec.branches

    def step(index, current_position, result):
        if index == len(branches):
            yield lmap.map(result), current_position
            return
        tag, child = branches[index]
        for conformed, next_position in _match_regex_all(
            child, values, current_position, path, via, location, problems
        ):
            yield from step(index + 1, next_position, {**result, tag: conformed})

    yield from step(0, position, {})


def _match_keys_star(spec, values, position, path, via, location, problems):
    for end in range(position, len(values) + 1, 2):
        if (end - position) % 2:
            continue
        mapped: dict[Any, Any] = {}
        valid_pairs = True
        for index in range(position, end, 2):
            key = values[index]
            if not isinstance(key, kw.Keyword):
                valid_pairs = False
                if problems is not None:
                    _invalid(
                        "keyword?",
                        key,
                        (*path, kw.keyword("k", ns="clojure.spec.alpha")),
                        via,
                        (*location, index),
                        problems,
                    )
                break
            mapped[key] = values[index + 1]
        if not valid_pairs:
            continue
        conformed = _conform_keys(
            spec.map_spec,
            lmap.map(mapped),
            path,
            via,
            location,
            problems,
        )
        if conformed is not INVALID:
            yield conformed, end


def _tagged_specs(
    name: str, tagged_specs: tuple[Any, ...]
) -> tuple[tuple[kw.Keyword, Any], ...]:
    if len(tagged_specs) % 2:
        raise ValueError(f"{name} requires tagged spec pairs")
    branches = []
    for tag, spec in zip(tagged_specs[::2], tagged_specs[1::2]):
        if not isinstance(tag, kw.Keyword):
            raise TypeError(f"{name} tags must be keywords")
        branches.append((tag, spec))
    return tuple(branches)


def _invalid(pred, value, path, via, location, problems):
    if problems is not None:
        problems.append(
            lmap.map(
                {
                    _PATH: vec.v(*path),
                    _PRED: pred,
                    _VAL: value,
                    _VIA: vec.v(*via),
                    _IN: vec.v(*location),
                }
            )
        )
    return INVALID


def _unform_regex(spec, value):
    if isinstance(spec, _Cat):
        if not _mapping(value):
            return [value]
        unformed = []
        for tag, child in spec.branches:
            unformed.extend(_unform_regex(child, value[tag]))
        return unformed
    if isinstance(spec, _Alt):
        if not _sequence(value) or len(value) != 2:
            return [value]
        tag, conformed = value
        for branch_tag, child in spec.branches:
            if branch_tag == tag:
                return _unform_regex(child, conformed)
        return [value]
    if isinstance(spec, _Repeat):
        if not _sequence(value):
            return [value]
        unformed = []
        for conformed in value:
            unformed.extend(_unform_regex(spec.spec, conformed))
        return unformed
    if isinstance(spec, _Maybe):
        return [] if value is None else _unform_regex(spec.spec, value)
    if isinstance(spec, _Amp):
        return _unform_regex(spec.spec, value)
    if isinstance(spec, _KeysStar):
        if not _mapping(value):
            return [value]
        unformed = []
        for key, item in value.items():
            unformed.extend((key, item))
        return unformed
    return [unform(spec, value)]


def _matches(pred: Any, value: Any) -> bool:
    return bool(pred(value)) if callable(pred) else value == pred


def _mapping(value: Any) -> bool:
    return isinstance(value, (Mapping, IPersistentMap))


def _sequence(value: Any) -> bool:
    return isinstance(value, (Sequence, ISequential)) and not isinstance(
        value, (bytes, str)
    )


def _regex_sequence(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(
        value, (bytes, str, Mapping, IPersistentMap)
    )
