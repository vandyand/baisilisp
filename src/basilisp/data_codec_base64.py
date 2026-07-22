"""Implementation kernel for ``basilisp.data.codec.base64``."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any, BinaryIO

_DECODE_TABLE = [0] * 256
for _value, _byte in enumerate(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
):
    _DECODE_TABLE[_byte] = _value


def enc_length(length: int) -> int:
    return _quot(int(length) + 2, 3) * 4


def dec_length(length: int, padding_length: int) -> int:
    return (_quot(int(length), 4) * 3) - int(padding_length)


def pad_length(source: bytes | bytearray | memoryview, offset: int, length: int) -> int:
    data = _slice(source, offset, length)
    if not data:
        return 0
    if data[-1] != ord("="):
        return 0
    return 2 if data[-2] == ord("=") else 1


def encode_into(
    source: bytes | bytearray | memoryview,
    offset: int,
    length: int,
    destination: bytearray | memoryview,
) -> int:
    encoded = base64.b64encode(_slice(source, offset, length))
    _write_destination(destination, encoded)
    return len(encoded)


def encode(
    source: bytes | bytearray | memoryview,
    offset: int | None = None,
    length: int | None = None,
) -> bytearray:
    if offset is None:
        offset, length = 0, len(source)
    if length is None:
        raise TypeError("encode requires both offset and length")
    return bytearray(base64.b64encode(_slice(source, offset, length)))


def decode_into(
    source: bytes | bytearray | memoryview,
    offset: int,
    length: int,
    destination: bytearray | memoryview,
) -> int:
    data = _slice(source, offset, length)
    decoded = _decode_bytes(data)
    _write_destination(destination, decoded)
    return len(decoded)


def decode(
    source: bytes | bytearray | memoryview,
    offset: int | None = None,
    length: int | None = None,
) -> bytearray:
    if offset is None:
        offset, length = 0, len(source)
    if length is None:
        raise TypeError("decode requires both offset and length")
    data = _slice(source, offset, length)
    return _decode_bytes(data)


def encoding_transfer(
    input_stream: BinaryIO, output_stream: BinaryIO, options: Any = None
) -> None:
    buffer_size = _buffer_size(options, 6144, 3)
    while data := _read_fully(input_stream, buffer_size):
        output_stream.write(base64.b64encode(data))


def decoding_transfer(
    input_stream: BinaryIO, output_stream: BinaryIO, options: Any = None
) -> None:
    buffer_size = _buffer_size(options, 8192, 4)
    while data := _read_fully(input_stream, buffer_size):
        output_stream.write(_decode_bytes(data))


def _decode_bytes(data: bytes) -> bytearray:
    decoded_length = dec_length(len(data), pad_length(data, 0, len(data)))
    output = bytearray(decoded_length)
    input_index = 0
    output_index = 0
    while output_index < decoded_length:
        bits = (
            (_DECODE_TABLE[data[input_index]] << 18)
            | (_DECODE_TABLE[data[input_index + 1]] << 12)
            | (_DECODE_TABLE[data[input_index + 2]] << 6)
            | _DECODE_TABLE[data[input_index + 3]]
        )
        input_index += 4
        output[output_index] = (bits >> 16) & 0xFF
        output_index += 1
        if output_index < decoded_length:
            output[output_index] = (bits >> 8) & 0xFF
            output_index += 1
        if output_index < decoded_length:
            output[output_index] = bits & 0xFF
            output_index += 1
    return output


def _read_fully(stream: BinaryIO, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunk = bytes(chunk)
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _buffer_size(options: Any, default: int, multiple: int) -> int:
    opts = _options(options)
    size = int(opts.get("buffer-size", default))
    if size < 0 or size % multiple:
        raise ValueError(f"Buffer size must be a multiple of {multiple}.")
    return size


def _options(options: Any) -> dict[str, Any]:
    if options is None:
        return {}
    if isinstance(options, Mapping):
        pairs = options.items()
    else:
        try:
            pairs = options.items()
        except AttributeError:
            return {}
    return {getattr(key, "name", str(key).lstrip(":")): value for key, value in pairs}


def _slice(source: bytes | bytearray | memoryview, offset: int, length: int) -> bytes:
    _validate_nonnegative(offset, "offset")
    _validate_nonnegative(length, "length")
    try:
        data = bytes(source)
    except TypeError as exc:
        raise TypeError("base64 input must be bytes-like") from exc
    if length == 0:
        return b""
    if offset + length > len(data):
        raise ValueError("offset and length exceed input size")
    return data[offset : offset + length]


def _write_destination(destination: bytearray | memoryview, data: bytes) -> None:
    if isinstance(destination, memoryview):
        if destination.readonly:
            raise TypeError("base64 output must be mutable")
    elif not isinstance(destination, bytearray):
        raise TypeError("base64 output must be a bytearray or writable memoryview")
    if len(destination) < len(data):
        raise ValueError("base64 output buffer is too small")
    destination[: len(data)] = data


def _validate_nonnegative(value: int, label: str) -> None:
    if int(value) < 0:
        raise ValueError(f"{label} must not be negative")


def _quot(numerator: int, denominator: int) -> int:
    if numerator < 0:
        return -((-numerator) // denominator)
    return numerator // denominator
