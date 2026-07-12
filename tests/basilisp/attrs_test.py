from __future__ import annotations

import attr
import pytest

from basilisp.lang import attrs as attrs_adapter
from basilisp.lang import keyword as kw


@attr.define
class Account:
    name: str
    level: int = attr.field(
        default=1,
        converter=int,
        validator=attr.validators.instance_of(int),
    )
    audit_code: str = attr.field(init=False, default="generated")


@attr.define
class AliasedAccount:
    _token: str = attr.field(alias="token")


def test_datafy_projects_declared_attrs_fields_without_conversion():
    account = Account("Ada", "2")

    projected = attrs_adapter.datafy(account)

    assert dict(projected) == {
        kw.keyword("name"): "Ada",
        kw.keyword("level"): 2,
        kw.keyword("audit_code"): "generated",
    }
    assert projected.meta[kw.keyword("obj", ns="basilisp.datafy")] is account
    assert projected.meta[kw.keyword("class", ns="basilisp.datafy")] == (
        attrs_adapter.class_symbol(Account)
    )


def test_from_data_uses_declared_names_and_attrs_constructor_rules():
    account = attrs_adapter.from_data(
        Account,
        {kw.keyword("name"): "Ada", kw.keyword("level"): "2"},
    )

    assert account == Account("Ada", 2)
    assert attrs_adapter.from_data(Account, {"name": "Grace"}) == Account("Grace")
    with pytest.raises(ValueError, match="non-init field"):
        attrs_adapter.from_data(
            Account,
            {kw.keyword("name"): "Ada", kw.keyword("audit_code"): "override"},
        )
    with pytest.raises(KeyError, match="unknown attrs field"):
        attrs_adapter.from_data(Account, {kw.keyword("unknown"): "value"})


def test_from_data_maps_attribute_names_to_constructor_aliases():
    account = attrs_adapter.from_data(
        AliasedAccount,
        {kw.keyword("_token"): "secret"},
    )

    assert account._token == "secret"
    with pytest.raises(KeyError, match="unknown attrs field"):
        attrs_adapter.from_data(AliasedAccount, {kw.keyword("token"): "secret"})


def test_attrs_adapter_rejects_invalid_inputs():
    with pytest.raises(TypeError, match="attrs instance"):
        attrs_adapter.datafy(Account)
    with pytest.raises(TypeError, match="attrs instance"):
        attrs_adapter.datafy({"name": "Ada"})
    with pytest.raises(TypeError, match="attrs type"):
        attrs_adapter.from_data(dict, {})
    with pytest.raises(ValueError, match="unqualified"):
        attrs_adapter.from_data(Account, {kw.keyword("name", ns="model"): "Ada"})
    with pytest.raises(TypeError, match="keywords or strings"):
        attrs_adapter.from_data(Account, {1: "Ada"})


def test_public_basilisp_namespace_exposes_the_explicit_adapter():
    import basilisp.contrib.attrs as public

    projected = public.datafy(Account("Ada"))

    assert projected[kw.keyword("name")] == "Ada"
    assert public.from_data(Account, {kw.keyword("name"): "Grace"}) == Account("Grace")
