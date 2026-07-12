"""Host-Python stream helpers for the remote pREPL server."""

from __future__ import annotations

import io
from typing import TextIO


class SeekableTextReader(io.TextIOBase):
    """Add bounded seek support to an incremental, non-seekable text stream."""

    def __init__(self, source: TextIO, max_chars: int = 1_048_576):
        self._source = source
        self._max_chars = max_chars
        self._buffer = io.StringIO()
        self._position = 0
        self._eof = False

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            position = offset
        elif whence == io.SEEK_CUR:
            position = self._position + offset
        elif whence == io.SEEK_END:
            self._read_to_end()
            position = self._length() + offset
        else:
            raise ValueError(f"unsupported seek origin: {whence}")
        if position < 0 or position > self._length():
            raise ValueError("seek position is outside the buffered input")
        self._position = position
        return position

    def read(self, size: int | None = -1) -> str:
        if size is None or size < 0:
            self._read_to_end()
            size = self._length() - self._position
        else:
            self._ensure(self._position + size)

        self._buffer.seek(self._position)
        value = self._buffer.read(size)
        self._position += len(value)
        return value

    def _length(self) -> int:
        return len(self._buffer.getvalue())

    def _append(self, value: str) -> None:
        if self._length() + len(value) > self._max_chars:
            raise ValueError(
                f"pREPL input exceeds the {self._max_chars}-character limit"
            )
        self._buffer.seek(0, io.SEEK_END)
        self._buffer.write(value)

    def _ensure(self, end: int) -> None:
        while not self._eof and self._length() < end:
            value = self._source.read(max(1, end - self._length()))
            if not value:
                self._eof = True
            else:
                self._append(value)

    def _read_to_end(self) -> None:
        while not self._eof:
            value = self._source.read(4096)
            if not value:
                self._eof = True
            else:
                self._append(value)
