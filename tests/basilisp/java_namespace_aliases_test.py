import importlib
import pathlib

from hypothesis import given
from hypothesis import strategies as st

from basilisp import main
from basilisp.lang import runtime
from basilisp.lang import symbol as sym


def _io_file():
    main.init()
    importlib.import_module("basilisp.java.io")
    var = runtime.Var.find(sym.symbol("file", ns="basilisp.java.io"))
    assert var is not None
    return var.value


@given(
    st.lists(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_- ",
            min_size=1,
            max_size=32,
        ),
        min_size=1,
        max_size=8,
    )
)
def test_clojure_java_io_file_matches_pathlib_for_generated_path_segments(parts):
    assert pathlib.Path(*parts) == _io_file()(*parts)
