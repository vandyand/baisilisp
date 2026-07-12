"""Explicit dataclass-to-Basilisp-data adapters."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any, TypeVar, cast

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
    """Project a dataclass instance to a keyword-keyed Basilisp map.

    Projection is shallow and does not coerce field values or register protocol
    implementations. The returned map records source-object provenance in its
    metadata, matching :mod:`basilisp.datafy`.
    """
    _require_dataclass_instance(instance)
    values = {
        kw.keyword(field.name): getattr(instance, field.name)
        for field in dataclasses.fields(instance)
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
    """Construct dataclass ``cls`` from keyword- or string-keyed ``data``.

    The adapter passes supplied values through unchanged. Defaults and default
    factories remain the dataclass constructor's responsibility, while unknown
    and non-init fields are rejected explicitly.
    """
    _require_dataclass_type(cls)
    if not isinstance(data, Mapping):
        raise TypeError("dataclass data must be a mapping")

    fields = {field.name: field for field in dataclasses.fields(cast(Any, cls))}
    kwargs: dict[str, Any] = {}
    for key, value in data.items():
        name = _field_name(key)
        field = fields.get(name)
        if field is None:
            raise KeyError(f"unknown dataclass field: {name}")
        if not field.init:
            raise ValueError(f"cannot construct non-init field: {name}")
        kwargs[name] = value
    return cls(**kwargs)


def _field_name(key: Any) -> str:
    if isinstance(key, kw.Keyword):
        if key.ns is not None:
            raise ValueError(f"dataclass field keywords must be unqualified: {key}")
        return key.name
    if isinstance(key, str):
        return key
    raise TypeError("dataclass data keys must be keywords or strings")


def _require_dataclass_instance(instance: Any) -> None:
    if isinstance(instance, type) or not dataclasses.is_dataclass(instance):
        raise TypeError("expected a dataclass instance")


def _require_dataclass_type(cls: Any) -> None:
    if not isinstance(cls, type) or not dataclasses.is_dataclass(cls):
        raise TypeError("expected a dataclass type")
