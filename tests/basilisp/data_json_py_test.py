from basilisp.data_json import read
from basilisp.lang import map as lmap


class NonSeekableReader:
    def __init__(self, source: str):
        self._source = source

    def read(self) -> str:
        source, self._source = self._source, ""
        return source


def test_non_seekable_stream_retains_unread_json_suffix():
    reader = NonSeekableReader('{"one":1}{"two":2}')

    assert read(reader) == lmap.map({"one": 1})
    assert read(reader) == lmap.map({"two": 2})
