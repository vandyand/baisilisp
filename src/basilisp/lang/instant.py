"""RFC3339-like timestamp parsing shared by Basilisp instant APIs."""

from __future__ import annotations

import datetime
import re
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_TIMESTAMP = re.compile(
    r"(\d{4})(?:-(\d{2})(?:-(\d{2})(?:T(\d{2})(?::(\d{2})(?::(\d{2})"
    r"(?:\.(\d+))?)?)?)?)?)?(?:Z|([-+])(\d{2}):(\d{2}))?"
)


def parse_timestamp(new_instant: Callable[..., T], cs: str) -> T:
    """Parse ``cs`` and pass its ten timestamp components to ``new_instant``.

    The grammar mirrors ``clojure.instant/parse-timestamp``: trailing date and
    time components may be elided, and an absent timezone offset means UTC.
    Fractional seconds are right-padded or truncated to nanosecond precision.
    """
    if not isinstance(cs, str):
        raise TypeError("timestamp must be a string")
    match = _TIMESTAMP.fullmatch(cs)
    if match is None:
        raise ValueError(f"Unrecognized date/time syntax: {cs}")

    (
        years,
        months,
        days,
        hours,
        minutes,
        seconds,
        fraction,
        offset_sign,
        offset_hours,
        offset_minutes,
    ) = match.groups()
    nanoseconds = 0 if fraction is None else int((fraction + "000000000")[:9])
    return new_instant(
        int(years),
        1 if months is None else int(months),
        1 if days is None else int(days),
        0 if hours is None else int(hours),
        0 if minutes is None else int(minutes),
        0 if seconds is None else int(seconds),
        nanoseconds,
        -1 if offset_sign == "-" else 1 if offset_sign == "+" else 0,
        0 if offset_hours is None else int(offset_hours),
        0 if offset_minutes is None else int(offset_minutes),
    )


def validated(new_instance: Callable[..., T]) -> Callable[..., T]:
    """Wrap ``new_instance`` with timestamp component validation."""

    def construct(
        years: int,
        months: int,
        days: int,
        hours: int,
        minutes: int,
        seconds: int,
        nanoseconds: int,
        offset_sign: int,
        offset_hours: int,
        offset_minutes: int,
    ) -> T:
        if not 1 <= months <= 12:
            raise ValueError("month must be between 1 and 12")
        if not 1 <= days <= _days_in_month(years, months):
            raise ValueError("day is not valid for the supplied year and month")
        if not 0 <= hours <= 23:
            raise ValueError("hour must be between 0 and 23")
        if not 0 <= minutes <= 59:
            raise ValueError("minute must be between 0 and 59")
        if not 0 <= seconds <= (60 if minutes == 59 else 59):
            raise ValueError("second is not valid for the supplied minute")
        if not 0 <= nanoseconds <= 999_999_999:
            raise ValueError("nanosecond must be between 0 and 999999999")
        if not -1 <= offset_sign <= 1:
            raise ValueError("offset sign must be -1, 0, or 1")
        if not 0 <= offset_hours <= 23:
            raise ValueError("offset hour must be between 0 and 23")
        if not 0 <= offset_minutes <= 59:
            raise ValueError("offset minute must be between 0 and 59")
        return new_instance(
            years,
            months,
            days,
            hours,
            minutes,
            seconds,
            nanoseconds,
            offset_sign,
            offset_hours,
            offset_minutes,
        )

    return construct


def read_instant(cs: str) -> datetime.datetime:
    """Read ``cs`` as a timezone-aware Python datetime normalized to UTC.

    Python datetimes retain microseconds, so fractions finer than six decimal
    places are truncated. Leap seconds are rejected because ``datetime`` has no
    representable value for them.
    """
    return parse_timestamp(validated(_construct_datetime), cs)


def _days_in_month(year: int, month: int) -> int:
    if month == 2:
        return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    return 30 if month in {4, 6, 9, 11} else 31


def _construct_datetime(
    years: int,
    months: int,
    days: int,
    hours: int,
    minutes: int,
    seconds: int,
    nanoseconds: int,
    offset_sign: int,
    offset_hours: int,
    offset_minutes: int,
) -> datetime.datetime:
    offset = datetime.timedelta(
        hours=offset_sign * offset_hours, minutes=offset_sign * offset_minutes
    )
    value = datetime.datetime(
        years,
        months,
        days,
        hours,
        minutes,
        seconds,
        nanoseconds // 1_000,
        tzinfo=datetime.timezone(offset),
    )
    return value.astimezone(datetime.timezone.utc)
