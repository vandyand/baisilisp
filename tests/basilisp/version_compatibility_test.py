from concurrent.futures import ThreadPoolExecutor

from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import runtime
from basilisp.lang import symbol as sym


def _core_var(name: str):
    core = runtime.Namespace.get_or_create(runtime.CORE_NS_SYM)
    return core.find(sym.symbol(name))


def _expected_version(
    major: int,
    minor: int,
    incremental: int | None,
    qualifier: str | None,
    interim: bool,
) -> str:
    result = f"{major}.{minor}"
    if incremental is not None:
        result += f".{incremental}"
    if qualifier:
        result += f"-{qualifier}"
    if interim:
        result += "-SNAPSHOT"
    return result


def test_clojure_version_root_is_an_explicit_compatibility_target():
    version_var = _core_var("*clojure-version*")

    assert version_var.value == runtime.CLOJURE_COMPATIBILITY_VERSION
    assert version_var.value == lmap.map(
        {
            kw.keyword("major"): 1,
            kw.keyword("minor"): 12,
            kw.keyword("incremental"): 4,
            kw.keyword("qualifier"): None,
        }
    )
    assert _core_var("clojure-version").value() == "1.12.4"


@given(
    major=st.integers(),
    minor=st.integers(),
    incremental=st.one_of(st.none(), st.integers()),
    qualifier=st.one_of(st.none(), st.text()),
    interim=st.booleans(),
)
def test_clojure_version_preserves_dynamic_map_formatting(
    major: int,
    minor: int,
    incremental: int | None,
    qualifier: str | None,
    interim: bool,
):
    version = lmap.map(
        {
            kw.keyword("major"): major,
            kw.keyword("minor"): minor,
            kw.keyword("incremental"): incremental,
            kw.keyword("qualifier"): qualifier,
            kw.keyword("interim"): interim,
        }
    )

    with runtime.bindings({_core_var("*clojure-version*"): version}):
        actual = _core_var("clojure-version").value()

    assert actual == _expected_version(major, minor, incremental, qualifier, interim)


def test_clojure_version_bindings_are_isolated_under_parallel_rendering():
    version_var = _core_var("*clojure-version*")
    clojure_version = _core_var("clojure-version").value

    def render(value: int) -> str:
        version = lmap.map(
            {
                kw.keyword("major"): value,
                kw.keyword("minor"): value + 1,
                kw.keyword("incremental"): value + 2,
                kw.keyword("qualifier"): "parallel",
            }
        )
        with runtime.bindings({version_var: version}):
            return clojure_version()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(render, range(256)))

    assert results == [
        f"{value}.{value + 1}.{value + 2}-parallel" for value in range(256)
    ]
    assert clojure_version() == "1.12.4"
