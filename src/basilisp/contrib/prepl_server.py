"""Host-Python stream helpers for the pREPL server and client."""

from __future__ import annotations

import io
import math
import socket
import threading
from collections.abc import Callable
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

    def readline(self, size: int | None = -1) -> str:
        """Read one bounded line while preserving the seekable input view.

        ``TextIOBase``'s default implementation raises ``UnsupportedOperation``.
        Socket-server accept functions, unlike the reader/compiler path, commonly
        use ``readline`` directly, so it must observe the same buffer and limit.
        """
        remaining = None if size is None or size < 0 else size
        chunks: list[str] = []
        while remaining is None or remaining > 0:
            char = self.read(1)
            if not char:
                break
            chunks.append(char)
            if char == "\n":
                break
            if remaining is not None:
                remaining -= 1
        return "".join(chunks)

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


def forward_remote_prepl(
    host: str,
    port: int,
    in_reader: TextIO,
    on_event: Callable[[str], None],
    max_event_chars: int = 1_048_576,
    connect_timeout: float | None = None,
) -> None:
    """Forward a text stream to a pREPL socket and consume its EDN events.

    The event callback is called from a dedicated reader thread with one complete
    line (without its trailing newline).  Keeping reader and writer independent
    prevents a pREPL whose output fills the socket buffer from deadlocking the
    producer.  The function returns only after the input side is closed and all
    remote events have been consumed, so callback and protocol errors propagate
    to the caller instead of becoming orphaned daemon-thread failures.
    """
    if not isinstance(max_event_chars, int) or isinstance(max_event_chars, bool):
        raise ValueError("max-event-chars must be a positive integer")
    if max_event_chars <= 0:
        raise ValueError("max-event-chars must be a positive integer")
    if connect_timeout is not None and (
        not isinstance(connect_timeout, (int, float))
        or isinstance(connect_timeout, bool)
        or not math.isfinite(connect_timeout)
        or connect_timeout <= 0
    ):
        raise ValueError("connect-timeout must be a finite positive number when supplied")

    client = socket.create_connection((host, port), timeout=connect_timeout)
    client.settimeout(None)
    reader = client.makefile("r", encoding="utf-8", newline="")
    writer = client.makefile("w", encoding="utf-8", newline="")
    reader_error: list[BaseException] = []

    def close_socket() -> None:
        try:
            client.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def consume_events() -> None:
        try:
            while True:
                # A valid max-length event may have one trailing newline. Asking
                # for two additional characters distinguishes that case from an
                # overlong event without allocating the whole malicious line.
                line = reader.readline(max_event_chars + 2)
                if not line:
                    return
                event = line[:-1] if line.endswith("\n") else line
                if len(event) > max_event_chars or (
                    len(line) == max_event_chars + 2 and not line.endswith("\n")
                ):
                    raise ValueError(
                        f"pREPL event exceeds the {max_event_chars}-character limit"
                    )
                on_event(event)
        except BaseException as exc:  # propagate callbacks and decoder failures
            reader_error.append(exc)
            close_socket()

    consumer = threading.Thread(
        target=consume_events, name="basilisp.contrib.prepl/remote-prepl", daemon=True
    )
    consumer.start()
    writer_error: BaseException | None = None
    try:
        while True:
            chunk = in_reader.read(4096)
            if not chunk:
                break
            if not isinstance(chunk, str):
                raise TypeError("remote pREPL input reader must return text")
            writer.write(chunk)
            writer.flush()
        try:
            client.shutdown(socket.SHUT_WR)
        except OSError:
            if not reader_error:
                raise
    except BaseException as exc:
        writer_error = exc
        close_socket()
    finally:
        consumer.join()
        try:
            reader.close()
        finally:
            try:
                writer.close()
            finally:
                client.close()

    if reader_error:
        raise reader_error[0]
    if writer_error:
        raise writer_error
