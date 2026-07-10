"""Stateful regular-expression matching helpers for ``basilisp.core``."""

from __future__ import annotations

import re


class Matcher:
    """A small adapter matching the stateful portion of Java's ``Matcher`` API."""

    def __init__(self, pattern: re.Pattern[str] | str, string: str) -> None:
        self._matches = re.finditer(pattern, string)
        self._current: re.Match[str] | None = None

    def find(self) -> bool:
        """Advance to the next match and report whether one was found."""
        try:
            self._current = next(self._matches)
        except StopIteration:
            self._current = None
            return False
        return True

    def group(self, index: int = 0) -> str | None:
        """Return a group from the current match."""
        if self._current is None:
            raise ValueError("No current regular-expression match")
        return self._current.group(index)

    def groups(self) -> tuple[str | None, ...]:
        """Return the capture groups from the current match."""
        if self._current is None:
            raise ValueError("No current regular-expression match")
        return self._current.groups()
