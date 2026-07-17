import io
import random

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


def test_seekable_text_reader_supports_readline_and_seek():
    reader = SeekableTextReader(io.StringIO("first\nsecond\n"))

    assert reader.readline() == "first\n"
    assert reader.tell() == len("first\n")
    assert reader.readline(3) == "sec"
    assert reader.seek(len("first\n")) == len("first\n")
    assert reader.readline() == "second\n"


def test_seekable_text_reader_seeded_readline_fuzz():
    rng = random.Random(0x51EED)
    alphabet = "abc\n"

    for _ in range(128):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randrange(96)))
        size = rng.choice([-1, 0, 1, 2, 7, 31])
        expected = io.StringIO(text).readline(size)
        reader = SeekableTextReader(io.StringIO(text), max_chars=128)

        assert reader.readline(size) == expected
        assert reader.tell() == len(expected)
