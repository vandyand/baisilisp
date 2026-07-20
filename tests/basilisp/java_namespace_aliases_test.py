import importlib
import pathlib
import sys
import tempfile

from hypothesis import given
from hypothesis import strategies as st

from basilisp import main
from basilisp.lang import keyword as kw
from basilisp.lang import runtime
from basilisp.lang import symbol as sym


def _io_fn(name):
    main.init()
    importlib.import_module("basilisp.java.io")
    var = runtime.Var.find(sym.symbol(name, ns="basilisp.java.io"))
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
    assert pathlib.Path(*parts) == _io_fn("file")(*parts)


@given(
    scheme=st.sampled_from(["http", "https", "file"]),
    host=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=24),
    path=st.lists(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=16
        ),
        min_size=1,
        max_size=5,
    ),
)
def test_clojure_java_io_as_url_preserves_generated_url_components(scheme, host, path):
    value = f"{scheme}://{host}/{'/'.join(path)}"
    url = _io_fn("as-url")(value)

    assert scheme == url.scheme
    assert host == url.netloc
    assert f"/{'/'.join(path)}" == url.path


@given(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs",), blacklist_characters="\r\n"
        ),
        max_size=200,
    )
)
def test_clojure_java_io_resource_discovers_generated_import_path_files(content):
    with tempfile.TemporaryDirectory() as tempdir:
        resource_dir = pathlib.Path(tempdir, "assets")
        resource_dir.mkdir()
        resource_file = resource_dir / "payload.txt"
        resource_file.write_text(content, encoding="utf-8")
        sys.path.insert(0, tempdir)
        try:
            resource = _io_fn("resource")("assets/payload.txt")
            assert "file" == resource.scheme
            with _io_fn("reader")(resource, kw.keyword("encoding"), "utf-8") as reader:
                assert content == reader.read()
        finally:
            sys.path.remove(tempdir)
