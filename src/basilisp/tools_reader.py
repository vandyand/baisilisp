"""Compatibility support for :mod:`clojure.tools.reader`.

The public namespaces are implemented in Lisp, while this module owns the
stateful reader objects.  Reusing one :class:`~basilisp.lang.reader.StreamReader`
is important: creating a new one for every form would discard its parser
lookahead and skip input on successive reads.
"""

from __future__ import annotations

import io
import re
from typing import Any

from basilisp.lang import character
from basilisp.lang import reader as lreader


class PushbackReader:
    """A stateful, optionally source-logging wrapper around a text stream."""

    __slots__ = ("stream", "reader", "source_logging", "file_name")

    def __init__(
        self,
        stream: io.TextIOBase | str,
        pushback_depth: int = 5,
        file_name: str | None = None,
        source_logging: bool = False,
        init_line: int | None = None,
        init_column: int | None = None,
    ) -> None:
        if isinstance(stream, str):
            stream = io.StringIO(stream)
        if not hasattr(stream, "read"):
            raise TypeError("reader must be a string or readable text stream")
        self.stream = stream
        # Basilisp's parser itself needs more than one pushback character for
        # some reader macros, so retain at least its normal lookahead depth.
        self.reader = lreader.StreamReader(
            stream,
            pushback_depth=max(5, pushback_depth),
            init_line=init_line,
            init_column=init_column,
        )
        self.source_logging = source_logging
        self.file_name = file_name if file_name is not None else self.reader.name

    def read_char(self) -> str | None:
        char = self.reader.advance()
        return char or None

    def peek_char(self) -> str | None:
        char = self.reader.peek()
        return char or None

    def unread(self, _char: Any = None) -> None:
        self.reader.pushback()

    def _source_bounds(self) -> tuple[int, int]:
        try:
            raw_position = self.stream.tell()
        except (AttributeError, OSError) as exc:
            raise TypeError("source logging requires a seekable text stream") from exc
        return raw_position - self.reader.unread_count, raw_position

    def _source_between(self, start: int, end: int) -> str:
        try:
            raw_position = self.stream.tell()
            self.stream.seek(start)
            source = self.stream.read(end - start).strip()
            self.stream.seek(raw_position)
        except (AttributeError, OSError) as exc:
            raise TypeError("source logging requires a seekable text stream") from exc
        return source

    def read_form(
        self,
        eof_error: bool,
        eof_value: Any,
        resolver: Any,
        data_readers: Any,
        features: Any,
        process_reader_cond: bool,
        default_data_reader_fn: Any,
        with_source: bool = False,
        process_tagged_literals: bool = True,
    ) -> Any:
        start = self._source_bounds()[0] if with_source else 0
        ctx = lreader.ReaderContext(
            self.reader,
            resolver=resolver,
            data_readers=data_readers,
            eof=eof_value,
            features=features,
            process_reader_cond=process_reader_cond,
            process_tagged_literals=process_tagged_literals,
            default_data_reader_fn=default_data_reader_fn,
        )
        while True:
            form = lreader._read_next(ctx)  # pylint: disable=protected-access
            if form is ctx.eof:
                if eof_error:
                    raise EOFError
                return (eof_value, "") if with_source else eof_value
            if form is lreader.COMMENT or isinstance(form, lreader.Comment):
                continue
            if (
                isinstance(form, lreader.ReaderConditional)
                and ctx.should_process_reader_cond
            ):
                raise ctx.syntax_error(
                    f"Unexpected reader conditional '{repr(form)})'; "
                    "reader is configured to process reader conditionals"
                )
            if not with_source:
                return form
            end = self._source_bounds()[0]
            return form, self._source_between(start, end)


def _as_pushback_reader(reader: Any) -> PushbackReader:
    if isinstance(reader, PushbackReader):
        return reader
    return PushbackReader(reader)


def push_back_reader(reader: Any, buffer_length: int = 1) -> PushbackReader:
    return PushbackReader(reader, pushback_depth=buffer_length)


def string_reader(source: str) -> io.StringIO:
    return io.StringIO(source)


def string_reader_from_parts(source: str, _source_len: int, source_pos: int):
    reader = io.StringIO(source)
    reader.seek(source_pos)
    return reader


def string_push_back_reader(source: str, buffer_length: int = 1) -> PushbackReader:
    return PushbackReader(source, pushback_depth=buffer_length)


def input_stream_reader(stream: Any) -> io.TextIOBase:
    if isinstance(stream, (bytes, bytearray)):
        return io.TextIOWrapper(io.BytesIO(stream))
    return io.TextIOWrapper(stream)


def input_stream_push_back_reader(
    stream: Any, buffer_length: int = 1
) -> PushbackReader:
    return PushbackReader(input_stream_reader(stream), pushback_depth=buffer_length)


def indexing_push_back_reader(
    reader: Any, buffer_length: int = 1, file_name: str | None = None
) -> PushbackReader:
    return PushbackReader(reader, pushback_depth=buffer_length, file_name=file_name)


def indexing_push_back_reader_from_parts(
    reader: Any,
    line: int | None,
    column: int | None,
    file_name: str | None,
    buffer_length: int = 1,
) -> PushbackReader:
    return PushbackReader(
        reader,
        pushback_depth=buffer_length,
        file_name=file_name,
        init_line=line,
        init_column=None if column is None else max(0, column - 1),
    )


def source_logging_push_back_reader(
    reader: Any, buffer_length: int = 1, file_name: str | None = None
) -> PushbackReader:
    return PushbackReader(
        reader,
        pushback_depth=buffer_length,
        file_name=file_name,
        source_logging=True,
    )


def source_logging_push_back_reader_from_parts(
    reader: Any,
    line: int | None,
    column: int | None,
    file_name: str | None,
    buffer_length: int = 1,
) -> PushbackReader:
    return PushbackReader(
        reader,
        pushback_depth=buffer_length,
        file_name=file_name,
        source_logging=True,
        init_line=line,
        init_column=None if column is None else max(0, column - 1),
    )


def read_char(reader: Any) -> str | None:
    char = _as_pushback_reader(reader).read_char()
    return None if char is None else character.character(char)


def peek_char(reader: Any) -> str | None:
    char = _as_pushback_reader(reader).peek_char()
    return None if char is None else character.character(char)


def unread(reader: Any, char: Any = None) -> None:
    _as_pushback_reader(reader).unread(char)


def indexing_reader(reader: Any) -> bool:
    return isinstance(reader, PushbackReader)


def source_logging_reader(reader: Any) -> bool:
    return isinstance(reader, PushbackReader) and reader.source_logging


def get_line_number(reader: Any) -> int | None:
    if not indexing_reader(reader):
        return None
    return reader.reader.line


def get_column_number(reader: Any) -> int | None:
    if not indexing_reader(reader):
        return None
    # Basilisp internally uses zero-based columns; tools.reader's API is one-based.
    return reader.reader.col + 1


def get_file_name(reader: Any) -> str | None:
    return reader.file_name if indexing_reader(reader) else None


def line_start(reader: Any) -> bool:
    return indexing_reader(reader) and reader.reader.col == 0


def read_line(reader: Any) -> str | None:
    reader = _as_pushback_reader(reader)
    chars: list[str] = []
    while (char := reader.read_char()) is not None:
        if char == "\n":
            return "".join(chars)
        if char != "\r":
            chars.append(char)
    return "".join(chars) if chars else None


def read_form(
    reader: Any,
    eof_error: bool,
    eof_value: Any,
    resolver: Any,
    data_readers: Any,
    features: Any,
    process_reader_cond: bool,
    default_data_reader_fn: Any,
    process_tagged_literals: bool = True,
) -> Any:
    return _as_pushback_reader(reader).read_form(
        eof_error,
        eof_value,
        resolver,
        data_readers,
        features,
        process_reader_cond,
        default_data_reader_fn,
        process_tagged_literals=process_tagged_literals,
    )


def read_form_with_source(
    reader: Any,
    eof_error: bool,
    eof_value: Any,
    resolver: Any,
    data_readers: Any,
    features: Any,
    process_reader_cond: bool,
    default_data_reader_fn: Any,
    process_tagged_literals: bool = True,
) -> tuple[Any, str]:
    reader = _as_pushback_reader(reader)
    if not reader.source_logging:
        raise TypeError("read+string requires a source-logging push-back reader")
    return reader.read_form(
        eof_error,
        eof_value,
        resolver,
        data_readers,
        features,
        process_reader_cond,
        default_data_reader_fn,
        process_tagged_literals=process_tagged_literals,
        with_source=True,
    )


def read_regex(reader: Any, _char: Any = None, _opts: Any = None, _pending: Any = None):
    """Read the body of a ``#\"...\"`` regex literal from a pushback reader."""
    reader = _as_pushback_reader(reader)
    chars: list[str] = []
    while (char := reader.read_char()) is not None:
        if char == '"':
            return re.compile("".join(chars))
        chars.append(char)
        if char == "\\":
            escaped = reader.read_char()
            if escaped is None:
                break
            chars.append(escaped)
    raise SyntaxError("Unexpected EOF while reading regex")


def syntax_quote(
    form: Any,
    resolver: Any,
    data_readers: Any,
    features: Any,
    process_reader_cond: bool,
    default_data_reader_fn: Any,
) -> Any:
    return lreader.syntax_quote(
        form,
        resolver=resolver,
        data_readers=data_readers,
        features=features,
        process_reader_cond=process_reader_cond,
        default_data_reader_fn=default_data_reader_fn,
    )
