"""Python-hosted kernel for the portable ``basilisp.data.json`` namespace.

The public namespace is deliberately Lisp code.  This module isolates the
stream cursor and JSON codec details that Python's standard library handles
well while returning Basilisp persistent values at its boundary.
"""

from __future__ import annotations

import datetime as dt
import decimal
import fractions
import io
import json
import math
import uuid
from collections.abc import Iterable, Mapping
from typing import Any, Callable

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import vector as lvec
from basilisp.lang.exception import ExceptionInfo
from basilisp.lang.symbol import Symbol


class _JSONObject(list):
    """Distinguish object pairs from JSON arrays during recursive conversion."""


# Python text streams do not have a PushbackReader equivalent. Seekable streams
# are rewound below; for non-seekable streams, retain only the unread suffix so
# successive data.json/read calls have the same single-value contract.
_PENDING_STREAM_TEXT: dict[int, tuple[Any, str]] = {}


def _keyword(name: str):
    return kw.keyword(name)


def _options(options: Any) -> dict[str, Any]:
    if options is None:
        return {}
    try:
        pairs = options.items()
    except AttributeError:
        return {}
    return {getattr(key, "name", str(key).lstrip(":")): value for key, value in pairs}


def _persistent(
    value: Any, key_fn: Callable[[str], Any], value_fn: Callable[[Any, Any], Any]
):
    if isinstance(value, _JSONObject):
        values: dict[Any, Any] = {}
        for raw_key, raw_value in value:
            key = key_fn(raw_key)
            transformed = value_fn(key, _persistent(raw_value, key_fn, value_fn))
            # data.json's established sentinel is the value-fn itself.
            if transformed is not value_fn:
                values[key] = transformed
        return lmap.map(values)
    if isinstance(value, list):
        return lvec.vector(_persistent(item, key_fn, value_fn) for item in value)
    return value


def _decoder(bigdec: bool) -> json.JSONDecoder:
    def reject_non_json_constant(value: str):
        raise ValueError(f"JSON error (unexpected token): {value}")

    return json.JSONDecoder(
        object_pairs_hook=_JSONObject,
        parse_float=decimal.Decimal if bigdec else float,
        parse_constant=reject_non_json_constant,
    )


def _decode_text(source: str, options: dict[str, Any]):
    eof_error = options.get("eof-error?", True)
    eof_value = options.get("eof-value")
    start = len(source) - len(source.lstrip())
    if start == len(source):
        if eof_error:
            raise EOFError("JSON error (end-of-file)")
        return eof_value, len(source)
    value, end = _decoder(bool(options.get("bigdec", False))).raw_decode(source, start)
    key_fn = options.get("key-fn") or (lambda key: key)
    value_fn = options.get("value-fn") or (lambda _key, value: value)
    return _persistent(value, key_fn, value_fn), end


def _handle_extra(value: Any, source: str, end: int, options: dict[str, Any]):
    extra = source[end:]
    if extra.strip() and (extra_fn := options.get("extra-data-fn")):
        return extra_fn(value, io.StringIO(extra))
    return value


def read_str(source: str, options: Any = None):
    opts = _options(options)
    value, end = _decode_text(source, opts)
    return _handle_extra(value, source, end, opts)


def read(reader: Any, options: Any = None):
    """Read one value and restore a seekable reader to just after that value."""

    opts = _options(options)
    try:
        start = reader.tell()
    except (AttributeError, OSError):
        start = None
    pending = _PENDING_STREAM_TEXT.pop(id(reader), None)
    source = pending[1] if pending and pending[0] is reader else reader.read()
    value, end = _decode_text(source, opts)
    if start is not None:
        try:
            reader.seek(start + end)
        except (AttributeError, OSError):
            pass
    elif not opts.get("extra-data-fn") and source[end:]:
        _PENDING_STREAM_TEXT[id(reader)] = (reader, source[end:])
    return _handle_extra(value, source, end, opts)


def on_extra_throw(value: Any, _reader: Any):
    raise ExceptionInfo(
        "Found extra data after json object", lmap.map({_keyword("val"): value})
    )


def on_extra_throw_remaining(value: Any, reader: Any):
    remaining = reader.read()
    raise ExceptionInfo(
        f"Found extra data after json object: {remaining}",
        lmap.map({_keyword("val"): value, _keyword("remaining"): remaining}),
    )


def _write_key(key: Any, key_fn: Callable[[Any], Any]) -> str:
    result = key_fn(key)
    if not isinstance(result, str):
        raise TypeError("JSON object keys must be strings")
    return result


def _default_key(value: Any) -> str:
    if isinstance(value, (kw.Keyword, Symbol)):
        return value.name
    if value is None:
        raise Exception("JSON object properties may not be nil")
    return str(value)


def _json_string(value: str, options: dict[str, Any]) -> str:
    result = json.dumps(value, ensure_ascii=bool(options.get("escape-unicode", True)))
    if options.get("escape-slash", True):
        result = result.replace("/", "\\/")
    if options.get("escape-js-separators", True):
        result = result.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return result


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping) or hasattr(value, "items")


def _write(value: Any, options: dict[str, Any], depth: int) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _json_string(value, options)
    if isinstance(value, (kw.Keyword, Symbol)):
        return _json_string(value.name, options)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, fractions.Fraction):
        return _write(float(value), options, depth)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON error: cannot write infinite or NaN float")
        return repr(value)
    if isinstance(value, uuid.UUID):
        return _json_string(str(value), options)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return _json_string(value.isoformat(), options)

    if _is_mapping(value):
        key_fn = options["key-fn"]
        value_fn = options["value-fn"]
        items = []
        for key, item in value.items():
            transformed = value_fn(key, item)
            if transformed is not value_fn:
                items.append(
                    (_write_key(key, key_fn), _write(transformed, options, depth + 1))
                )
        if not items:
            return "{}"
        if not options.get("indent", False):
            return (
                "{"
                + ",".join(
                    _json_string(key, options) + ":" + item for key, item in items
                )
                + "}"
            )
        prefix = "  " * (depth + 1)
        suffix = "  " * depth
        return (
            "{\n"
            + ",\n".join(
                prefix + _json_string(key, options) + ": " + item for key, item in items
            )
            + "\n"
            + suffix
            + "}"
        )

    if isinstance(value, Iterable):
        items = [_write(item, options, depth + 1) for item in value]
        if not items:
            return "[]"
        if not options.get("indent", False):
            return "[" + ",".join(items) + "]"
        prefix = "  " * (depth + 1)
        suffix = "  " * depth
        return "[\n" + ",\n".join(prefix + item for item in items) + "\n" + suffix + "]"

    writer = io.StringIO()
    options["default-write-fn"](
        value, writer, lmap.map({_keyword(k): v for k, v in options.items()})
    )
    return writer.getvalue()


def write_str(value: Any, options: Any = None) -> str:
    opts = {
        "escape-unicode": True,
        "escape-js-separators": True,
        "escape-slash": True,
        "key-fn": _default_key,
        "value-fn": lambda _key, item: item,
        "default-write-fn": _default_write,
        "indent": False,
    }
    opts.update(_options(options))
    return _write(value, opts, 0)


def _default_write(value: Any, _writer: Any, _options: Any):
    raise TypeError(f"Don't know how to write JSON of {type(value).__name__}")


def write(value: Any, writer: Any, options: Any = None):
    writer.write(write_str(value, options))
