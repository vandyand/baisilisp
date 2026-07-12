"""Portable descriptor-based validation used by ``basilisp.spec.alpha``."""

from __future__ import annotations

import functools
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import vector as vec
from basilisp.lang.exception import ExceptionInfo
from basilisp.lang.interfaces import IPersistentMap, IPersistentSet
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
class _Instrumented:
    original: Callable[..., Any]
    module_name: str
    module_value: Any
    wrapper: Callable[..., Any]


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
    required: tuple[kw.Keyword, ...]
    optional: tuple[kw.Keyword, ...]


@dataclass(frozen=True)
class _Tuple(_Spec):
    specs: tuple[Any, ...]


@dataclass(frozen=True)
class _MultiSpec(_Spec):
    dispatch: Callable[[Any], kw.Keyword]


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


def fspec(
    *, args: Any | None = None, ret: Any | None = None, fn: Any | None = None
) -> _FSpec:
    """Create a descriptor for a callable's argument, return, and relation specs."""
    return _FSpec(args, ret, fn)


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
        _validate_function_value(target, ":args", function_spec.args, call_args)

    result = original(*args, **kwargs)
    if function_spec.ret is not None:
        _validate_function_value(target, ":ret", function_spec.ret, result)
    if function_spec.fn is not None:
        _validate_function_value(
            target,
            ":fn",
            function_spec.fn,
            lmap.map({_CALL_ARGS: call_args, _CALL_RET: result}),
        )
    return result


def _validate_function_value(target: Var, role: str, contract: Any, value: Any) -> None:
    details = explain_data(contract, value)
    if details is None:
        return
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


def keys(
    required: Iterable[kw.Keyword] = (), optional: Iterable[kw.Keyword] = ()
) -> _Keys:
    return _Keys(tuple(required), tuple(optional))


def tuple_(*specs: Any) -> _Tuple:
    return _Tuple(specs)


def multi_spec(dispatch: Callable[[Any], kw.Keyword]) -> _MultiSpec:
    return _MultiSpec(dispatch)


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
            selected = spec.dispatch(value)
        except BaseException:
            selected = None
        if not isinstance(selected, kw.Keyword):
            return _invalid(spec.dispatch, value, path, via, location, problems)
        return _conform(selected, value, path, via, location, problems)
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
    for key in spec.required:
        if key not in value:
            return _invalid(key, value, path, via, location, problems)
    for key in (*spec.required, *spec.optional):
        if (
            key in value
            and _conform(key, value[key], path, via, (*location, key), problems)
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
    matched = _match_regex(spec, values, 0, path, via, location, problems)
    if matched is None:
        return INVALID
    conformed, position = matched
    if position != len(values):
        return _invalid(spec, value, path, via, (*location, position), problems)
    return conformed


def _match_regex(spec, values, position, path, via, location, problems):
    if isinstance(spec, _Cat):
        result: dict[kw.Keyword, Any] = {}
        for tag, child in spec.branches:
            matched = _match_regex(
                child, values, position, path, via, location, problems
            )
            if matched is None:
                return None
            conformed, position = matched
            result[tag] = conformed
        return lmap.map(result), position
    if isinstance(spec, _Alt):
        for tag, child in spec.branches:
            matched = _match_regex(child, values, position, path, via, location, None)
            if matched is not None:
                conformed, next_position = matched
                return vec.v(tag, conformed), next_position
        if problems is not None:
            for _tag, child in spec.branches:
                _match_regex(child, values, position, path, via, location, problems)
        if position >= len(values):
            _invalid(spec, None, path, via, (*location, position), problems)
        return None
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
            return None
        return vec.v(*matches), position
    if isinstance(spec, _Maybe):
        matched = _match_regex(spec.spec, values, position, path, via, location, None)
        return (None, position) if matched is None else matched
    if isinstance(spec, _Amp):
        matched = _match_regex(
            spec.spec, values, position, path, via, location, problems
        )
        if matched is None:
            return None
        conformed, next_position = matched
        for predicate in spec.predicates:
            conformed = _conform(
                predicate, conformed, path, via, (*location, position), problems
            )
            if conformed is INVALID:
                return None
        return conformed, next_position
    if position >= len(values):
        _invalid(spec, None, path, via, (*location, position), problems)
        return None
    conformed = _conform(
        spec, values[position], path, via, (*location, position), problems
    )
    if conformed is INVALID:
        return None
    return conformed, position + 1


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
    return [unform(spec, value)]


def _matches(pred: Any, value: Any) -> bool:
    return bool(pred(value)) if callable(pred) else value == pred


def _mapping(value: Any) -> bool:
    return isinstance(value, (Mapping, IPersistentMap))


def _sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (bytes, str))


def _regex_sequence(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(
        value, (bytes, str, Mapping, IPersistentMap)
    )
