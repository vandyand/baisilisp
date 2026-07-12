from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from basilisp.lang import dataclass as dataclass_adapter
from basilisp.lang import keyword as kw


@dataclass
class Account:
    name: str
    active: bool = True
    audit_code: str = field(init=False, default="generated")


def test_datafy_projects_declared_fields_without_coercion_and_keeps_provenance():
    account = Account("Ada")

    projected = dataclass_adapter.datafy(account)

    assert dict(projected) == {
        kw.keyword("name"): "Ada",
        kw.keyword("active"): True,
        kw.keyword("audit_code"): "generated",
    }
    assert projected.meta[kw.keyword("obj", ns="basilisp.datafy")] is account
    assert projected.meta[kw.keyword("class", ns="basilisp.datafy")] == (
        dataclass_adapter.class_symbol(Account)
    )


def test_from_data_uses_only_init_fields_and_dataclass_defaults():
    account = dataclass_adapter.from_data(Account, {kw.keyword("name"): "Ada"})

    assert account == Account("Ada")
    with pytest.raises(ValueError, match="non-init field"):
        dataclass_adapter.from_data(
            Account,
            {kw.keyword("name"): "Ada", kw.keyword("audit_code"): "override"},
        )
    with pytest.raises(KeyError, match="unknown dataclass field"):
        dataclass_adapter.from_data(Account, {kw.keyword("unknown"): "value"})


def test_dataclass_adapter_rejects_classes_and_non_dataclass_inputs():
    with pytest.raises(TypeError, match="dataclass instance"):
        dataclass_adapter.datafy(Account)
    with pytest.raises(TypeError, match="dataclass instance"):
        dataclass_adapter.datafy({"name": "Ada"})
    with pytest.raises(TypeError, match="dataclass type"):
        dataclass_adapter.from_data(dict, {})


def test_public_basilisp_namespace_exposes_the_explicit_adapter():
    import basilisp.contrib.dataclasses as public

    projected = public.datafy(Account("Ada"))

    assert projected[kw.keyword("name")] == "Ada"
    assert public.from_data(Account, {kw.keyword("name"): "Grace"}) == Account("Grace")
