import io

import pytest

from basilisp.contrib.prepl_server import SeekableTextReader


def test_seekable_text_reader_caches_and_rewinds_incrementally():
    reader = SeekableTextReader(io.StringIO("abcdef"))

    assert reader.read(2) == "ab"
    assert reader.tell() == 2
    assert reader.read(2) == "cd"
    assert reader.seek(1) == 1
    assert reader.read(4) == "bcde"
    assert reader.read() == "f"


def test_seekable_text_reader_enforces_input_limit():
    reader = SeekableTextReader(io.StringIO("abcdef"), max_chars=5)

    with pytest.raises(ValueError, match="input exceeds"):
        reader.read()
