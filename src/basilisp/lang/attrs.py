"""Explicit attrs-to-Basilisp-data adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

import attr

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import symbol as sym
from basilisp.lang.interfaces import IPersistentMap

T = TypeVar("T")

_DATAFY_OBJECT = kw.keyword("obj", ns="basilisp.datafy")
_DATAFY_CLASS = kw.keyword("class", ns="basilisp.datafy")


def class_symbol(cls: type[Any]) -> sym.Symbol:
    """Return the stable qualified symbol representing ``cls``."""
    return sym.symbol(f"{cls.__module__}.{cls.__qualname__}")


def datafy(instance: Any) -> IPersistentMap:
    """Project an attrs instance to a keyword-keyed Basilisp map.

    Projection is shallow and does not invoke attrs converters or validators.
    The returned map records source-object provenance in its metadata, matching
    :mod:`basilisp.datafy`.
    """
    _require_attrs_instance(instance)
    values = {
        kw.keyword(field.name): getattr(instance, field.name)
        for field in attr.fields(type(instance))
    }
    return lmap.map(
        values,
        meta=lmap.map(
            {
                _DATAFY_OBJECT: instance,
                _DATAFY_CLASS: class_symbol(type(instance)),
            }
        ),
    )


def from_data(cls: type[T], data: Mapping[Any, Any]) -> T:
    """Construct an attrs instance from keyword- or string-keyed ``data``.

    Keys name declared attributes, not constructor aliases. Values are passed to
    the generated attrs initializer unchanged; its documented converters run
    before validators, defaults remain the initializer's responsibility, and
    unknown or non-init fields are rejected explicitly.
    """
    _require_attrs_type(cls)
    if not isinstance(data, Mapping):
        raise TypeError("attrs data must be a mapping")

    fields = {field.name: field for field in attr.fields(cast(Any, cls))}
    kwargs: dict[str, Any] = {}
    for key, value in data.items():
        name = _field_name(key)
        field = fields.get(name)
        if field is None:
            raise KeyError(f"unknown attrs field: {name}")
        if not field.init:
            raise ValueError(f"cannot construct non-init field: {name}")
        kwargs[field.alias] = value
    return cls(**kwargs)


def _field_name(key: Any) -> str:
    if isinstance(key, kw.Keyword):
        if key.ns is not None:
            raise ValueError(f"attrs field keywords must be unqualified: {key}")
        return key.name
    if isinstance(key, str):
        return key
    raise TypeError("attrs data keys must be keywords or strings")


def _require_attrs_instance(instance: Any) -> None:
    if isinstance(instance, type) or not attr.has(type(instance)):
        raise TypeError("expected an attrs instance")


def _require_attrs_type(cls: Any) -> None:
    if not isinstance(cls, type) or not attr.has(cls):
        raise TypeError("expected an attrs type")
