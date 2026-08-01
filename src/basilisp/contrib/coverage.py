"""coverage.py support for Basilisp source files.

The Basilisp compiler uses ``.lpy`` source filenames in generated Python code
objects.  coverage.py still needs a plug-in so measured ``.lpy`` files are
reported as Basilisp source instead of being parsed as Python.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from types import FrameType
from typing import Any

from coverage.plugin import CoveragePlugin, FileReporter, FileTracer

from basilisp.lang import keyword as kw
from basilisp.lang import reader

_LPY_SUFFIX = ".lpy"
_LINE = kw.keyword("line", ns="basilisp.lang.reader")
_END_LINE = kw.keyword("end-line", ns="basilisp.lang.reader")


def _looks_like_lpy(filename: str) -> bool:
    """Return whether ``filename`` names a concrete Basilisp source file."""
    if filename.startswith("<") and filename.endswith(">"):
        return False
    path = Path(filename)
    return path.suffix == _LPY_SUFFIX and path.is_file()


def _normalize_filename(filename: str) -> str:
    """Normalize concrete paths while preserving coverage.py's filename shape."""
    try:
        return os.path.realpath(filename)
    except (OSError, ValueError):  # pragma: no cover - defensive for odd paths
        return filename


def _source_lines(filename: str) -> list[str]:
    with open(filename, encoding="utf-8") as f:
        return f.read().splitlines()


def _fallback_executable_lines(lines: list[str]) -> set[int]:
    """Conservative executable-line fallback for malformed source.

    Coverage often runs while users are editing files. If the reader cannot parse
    a file, report non-empty, non-comment physical lines rather than failing the
    entire coverage report.
    """
    executable: set[int] = set()
    for line_no, source_line in enumerate(lines, start=1):
        stripped = source_line.lstrip()
        if stripped and not stripped.startswith(";"):
            executable.add(line_no)
    return executable


def _form_source_lines(source: str, physical_lines: list[str]) -> tuple[set[int], bool]:
    executable: set[int] = set()
    saw_unlocated_form = False
    for form in reader.read_str(
        source,
        resolver=None,
        process_reader_cond=True,
        process_tagged_literals=False,
    ):
        meta = getattr(form, "meta", None)
        if meta is None:
            saw_unlocated_form = True
            continue
        start = meta.val_at(_LINE)
        end = meta.val_at(_END_LINE) or start
        if start is None:
            saw_unlocated_form = True
            continue
        for line_no in range(start, end + 1):
            if 1 <= line_no <= len(physical_lines):
                stripped = physical_lines[line_no - 1].lstrip()
                if stripped and not stripped.startswith(";"):
                    executable.add(line_no)
    return executable, saw_unlocated_form


def executable_lines(filename: str) -> set[int]:
    """Return executable line numbers for a Basilisp source file."""
    physical_lines = _source_lines(filename)
    source = "\n".join(physical_lines)
    if source and not source.endswith("\n"):
        source = f"{source}\n"
    try:
        lines, saw_unlocated_form = _form_source_lines(source, physical_lines)
        if saw_unlocated_form:
            lines.update(_fallback_executable_lines(physical_lines))
        return lines
    except Exception:  # pylint: disable=broad-exception-caught
        return _fallback_executable_lines(physical_lines)


class BasilispFileTracer(FileTracer):
    """Trace a Python frame whose code object came from a Basilisp source file."""

    def __init__(self, filename: str) -> None:
        self._filename = _normalize_filename(filename)
        self._executable_lines = executable_lines(self._filename)

    def source_filename(self) -> str:
        return self._filename

    def line_number_range(self, frame: FrameType) -> tuple[int, int]:
        line_no = frame.f_lineno
        if line_no <= 0 or line_no not in self._executable_lines:
            return -1, -1
        return line_no, line_no


class BasilispFileReporter(FileReporter):
    """Report executable lines and source text for a Basilisp source file."""

    def __init__(self, filename: str) -> None:
        super().__init__(_normalize_filename(filename))

    def lines(self) -> set[int]:
        return executable_lines(self.filename)


class BasilispCoveragePlugin(CoveragePlugin):
    """coverage.py plug-in for ``.lpy`` source files."""

    def file_tracer(self, filename: str) -> FileTracer | None:
        if _looks_like_lpy(filename):
            return BasilispFileTracer(filename)
        return None

    def file_reporter(self, filename: str) -> FileReporter:
        return BasilispFileReporter(filename)

    def find_executable_files(self, src_dir: str) -> Iterable[str]:
        root = Path(src_dir)
        if not root.exists():
            return []
        return (
            str(path)
            for path in root.rglob(f"*{_LPY_SUFFIX}")
            if path.is_file() and not path.name.startswith(".")
        )

    def sys_info(self) -> Iterable[tuple[str, Any]]:
        return [("lpy_suffix", _LPY_SUFFIX)]


def coverage_init(reg: Any, options: dict[str, Any] | None = None) -> None:
    """Register the Basilisp coverage.py plug-in."""
    reg.add_file_tracer(BasilispCoveragePlugin())
