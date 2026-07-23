"""Python logging bridge for ``basilisp.tools.logging``."""

from __future__ import annotations

import logging
import sys
import importlib
from typing import Any

from basilisp import logconfig

LEVELS = {
    "trace": logconfig.TRACE,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.CRITICAL,
}


def level_number(level: Any) -> int:
    name = getattr(level, "name", str(level).lstrip(":"))
    try:
        return LEVELS[name.lower()]
    except KeyError as exc:
        raise ValueError(f"Unknown logging level: {level}") from exc


def get_logger(logger_ns: Any) -> logging.Logger:
    return logging.getLogger(str(logger_ns))


def class_found(name: Any) -> bool:
    parts = str(name).split(".")
    for end in range(len(parts), 0, -1):
        try:
            importlib.import_module(".".join(parts[:end]))
            return True
        except Exception:  # pragma: no cover - mirrors Clojure's probing helper
            continue
    return False


def write(
    logger: logging.Logger, level: Any, throwable: BaseException | None, message: Any
):
    logger.log(level_number(level), str(message), exc_info=throwable)


class LogWriter:
    """A text writer that sends complete lines to a Python logger."""

    def __init__(self, level: Any, logger_ns: Any):
        self._logger = get_logger(logger_ns)
        self._level = level
        self._parts: list[str] = []

    def write(self, text: Any) -> int:
        text = str(text)
        self._parts.append(text)
        while "\n" in "".join(self._parts):
            buffered = "".join(self._parts)
            line, buffered = buffered.split("\n", maxsplit=1)
            self._parts = [buffered]
            if line:
                write(self._logger, self._level, None, line)
        return len(text)

    def flush(self) -> None:
        message = "".join(self._parts).strip()
        self._parts.clear()
        if message:
            write(self._logger, self._level, None, message)


_original_streams: tuple[Any, Any] | None = None


def log_stream(level: Any, logger_ns: Any) -> LogWriter:
    return LogWriter(level, logger_ns)


def capture(logger_ns: Any, out_level: Any = "info", err_level: Any = "error") -> None:
    global _original_streams
    if _original_streams is None:
        _original_streams = (sys.stdout, sys.stderr)
    sys.stdout = log_stream(out_level, logger_ns)
    sys.stderr = log_stream(err_level, logger_ns)


def uncapture() -> None:
    global _original_streams
    if _original_streams is not None:
        sys.stdout, sys.stderr = _original_streams
        _original_streams = None
