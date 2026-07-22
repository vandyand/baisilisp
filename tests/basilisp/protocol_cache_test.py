from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from basilisp.lang import keyword as kw
from basilisp.lang import runtime
from tests.basilisp.helpers import CompileFn


@pytest.fixture
def test_ns() -> str:
    return "protocol-cache-test"


@pytest.fixture
def compiler_file_path() -> str:
    return "<protocol cache test>"


class Interface:
    pass


class ExternalBase:
    pass


class ExternalChild(ExternalBase):
    pass


def _default(_obj):
    raise LookupError("no protocol implementation")


def _direct(_obj):
    return "direct"


def _external(_obj):
    return "external"


def test_protocol_dispatch_resolves_direct_and_extended_methods_without_invoking_them():
    dispatch = runtime.ProtocolDispatch(_default, Interface)
    direct = type("Direct", (Interface,), {})()
    external = ExternalChild()

    assert dispatch.resolve_cached(direct, Interface, _direct) is _direct
    assert dispatch.resolve_cached(external, Interface, _direct) is None

    dispatch.register(ExternalBase, _external)
    assert dispatch.resolve_cached(external, Interface, _direct) is _external
    dispatch.clear_cache()
    assert dispatch.resolve_cached(external, Interface, _direct) is _external


def test_protocol_dispatch_rejects_invalid_cache_helper_inputs():
    dispatch = runtime.ProtocolDispatch(_default, Interface)
    with pytest.raises(TypeError, match="interface"):
        dispatch.resolve_cached(ExternalChild(), "not-a-type", _direct)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="callable"):
        dispatch.resolve_cached(ExternalChild(), Interface, "not-callable")  # type: ignore[arg-type]


@given(depth=st.integers(min_value=1, max_value=16), register_at=st.integers(0, 15))
@settings(max_examples=150, deadline=None)
def test_protocol_dispatch_fuzzes_inherited_extension_resolution(
    depth: int, register_at: int
):
    register_at %= depth
    classes = [type("Root", (), {})]
    for index in range(1, depth):
        classes.append(type(f"Derived{index}", (classes[-1],), {}))

    dispatch = runtime.ProtocolDispatch(_default, Interface)
    dispatch.register(classes[register_at], _external)
    value = classes[-1]()
    assert dispatch.resolve_cached(value, Interface, _direct) is _external
    dispatch.clear_cache()
    assert dispatch.resolve_cached(value, Interface, _direct) is _external


def test_protocol_dispatch_cache_reset_is_safe_under_concurrent_resolution():
    dispatch = runtime.ProtocolDispatch(_default, Interface)
    dispatch.register(ExternalBase, _external)
    value = ExternalChild()

    def resolve_and_reset(_index: int) -> None:
        for _ in range(200):
            assert dispatch.resolve_cached(value, Interface, _direct) is _external
            assert (
                dispatch.resolve_cached(value, Interface, _direct)(value) == "external"
            )
            dispatch.clear_cache()

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(resolve_and_reset, range(128)))


def test_core_protocol_cache_helpers_match_protocol_dispatch_contract(
    lcompile: CompileFn,
):
    lcompile("""
        (defprotocol CacheProbe (cache-probe [this]))
        (defrecord DirectProbe [] CacheProbe (cache-probe [_] :direct))
        (defrecord ExtendedProbe [])
        (extend ExtendedProbe CacheProbe {:cache-probe (fn [_] :extended)})
        """)
    assert lcompile("(cache-probe (->DirectProbe))") == kw.keyword("direct")
    assert lcompile("(cache-probe (->ExtendedProbe))") == kw.keyword("extended")
    assert lcompile("(-reset-methods CacheProbe)") is None
    assert lcompile("(cache-probe (->DirectProbe))") == kw.keyword("direct")
    assert lcompile("(cache-probe (->ExtendedProbe))") == kw.keyword("extended")
    assert lcompile("""
        (let [f (-cache-protocol-fn cache-probe
                                    (->DirectProbe)
                                    (:interface CacheProbe)
                                    (fn [_] :direct-interface))]
          (f (->DirectProbe)))
        """) == kw.keyword("direct-interface")
    assert lcompile("""
        (let [f (-cache-protocol-fn cache-probe
                                    (->ExtendedProbe)
                                    (:interface CacheProbe)
                                    (fn [_] :direct-interface))]
          (f (->ExtendedProbe)))
        """) == kw.keyword("extended")
    with pytest.raises(TypeError, match="ProtocolDispatch"):
        lcompile("(-cache-protocol-fn identity :value python/object identity)")
    with pytest.raises(TypeError, match="protocol"):
        lcompile("(-reset-methods {})")
