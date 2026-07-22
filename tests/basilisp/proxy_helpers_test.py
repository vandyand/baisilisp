from concurrent.futures import ThreadPoolExecutor

import pytest

from basilisp.lang import map as lmap
from basilisp.lang import runtime
from basilisp.lang import symbol as sym


class Describable:
    def describe(self):
        return "base"


def _core_fn(name: str):
    core = runtime.Namespace.get_or_create(runtime.CORE_NS_SYM)
    return core.find(sym.symbol(name)).value


def test_proxy_name_reports_the_cached_python_proxy_class_label():
    proxy_name = _core_fn("proxy-name")
    proxy_class = _core_fn("get-proxy-class")(Describable)

    assert proxy_name(Describable, ()) == (
        f"{proxy_class.__module__}.{proxy_class.__qualname__}"
    )
    assert proxy_name(Describable, ()) == proxy_name(Describable, ())
    assert proxy_name(Describable, ()) != proxy_name(object, ())


def test_proxy_call_with_super_restores_mappings_after_success_and_failure():
    proxy_class = _core_fn("get-proxy-class")(Describable)
    proxy_call_with_super = _core_fn("proxy-call-with-super")
    proxy = proxy_class(lmap.map({"describe": lambda _self: "override"}))

    assert proxy.describe() == "override"
    assert proxy_call_with_super(lambda: proxy.describe(), proxy, "describe") == "base"
    assert proxy.describe() == "override"

    with pytest.raises(RuntimeError, match="callback failed"):
        proxy_call_with_super(
            lambda: (_ for _ in ()).throw(RuntimeError("callback failed")),
            proxy,
            "describe",
        )

    assert proxy.describe() == "override"


def test_proxy_call_with_super_is_isolated_for_parallel_proxy_instances():
    proxy_class = _core_fn("get-proxy-class")(Describable)
    proxy_call_with_super = _core_fn("proxy-call-with-super")

    def exercise(value: int) -> tuple[str, str, str]:
        proxy = proxy_class(lmap.map({"describe": lambda _self: f"override-{value}"}))
        before = proxy.describe()
        super_value = proxy_call_with_super(lambda: proxy.describe(), proxy, "describe")
        after = proxy.describe()
        return before, super_value, after

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(exercise, range(256)))

    assert results == [
        (f"override-{value}", "base", f"override-{value}") for value in range(256)
    ]
