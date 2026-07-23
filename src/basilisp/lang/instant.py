"""RFC3339-like timestamp parsing shared by Basilisp instant APIs."""

from __future__ import annotations

import datetime
import re
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from typing import TypeVar

T = TypeVar("T")

_UTC = datetime.timezone.utc
_UNIX_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=_UTC)

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


class InstantDateTime(datetime.datetime):
    """Datetime subclass used for reader instants with exact timestamp arithmetic."""

    def timestamp(self) -> Fraction:  # type: ignore[override]
        return timestamp_seconds(self)


class InstantTimestamp(InstantDateTime):
    """Datetime subclass carrying Clojure timestamp nanosecond precision."""

    __slots__ = ("_nanoseconds",)

    def __new__(
        cls,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
        tzinfo: datetime.tzinfo | None = None,
        *,
        fold: int = 0,
        nanoseconds: int = 0,
    ) -> "InstantTimestamp":
        self = super().__new__(
            cls,
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            tzinfo=tzinfo,
            fold=fold,
        )
        self._nanoseconds = nanoseconds
        return self

    @property
    def nanoseconds(self) -> int:
        return self._nanoseconds


@dataclass(frozen=True)
class InstantCalendar:
    """Offset-preserving portable counterpart to ``java.util.Calendar``."""

    datetime: datetime.datetime
    nanoseconds: int
    offset_minutes: int

    @property
    def year(self) -> int:
        return self.datetime.year

    @property
    def month(self) -> int:
        return self.datetime.month

    @property
    def day(self) -> int:
        return self.datetime.day

    @property
    def hour(self) -> int:
        return self.datetime.hour

    @property
    def minute(self) -> int:
        return self.datetime.minute

    @property
    def second(self) -> int:
        return self.datetime.second

    @property
    def millisecond(self) -> int:
        return self.datetime.microsecond // 1_000

    def timestamp(self) -> Fraction:
        return timestamp_seconds(self.datetime)


def timestamp_seconds(value: datetime.datetime) -> Fraction:
    """Return exact seconds between ``value`` and the Unix epoch."""

    delta = value.astimezone(_UTC) - _UNIX_EPOCH
    micros = (
        (delta.days * 24 * 60 * 60) + delta.seconds
    ) * 1_000_000 + delta.microseconds
    return Fraction(micros, 1_000_000)


def epoch_millis(value: datetime.datetime) -> int:
    """Return exact integer milliseconds between ``value`` and the Unix epoch."""

    delta = value.astimezone(_UTC) - _UNIX_EPOCH
    micros = (
        (delta.days * 24 * 60 * 60) + delta.seconds
    ) * 1_000_000 + delta.microseconds
    return micros // 1_000


def read_instant_date(cs: str) -> datetime.datetime:
    """Read ``cs`` as a Date-like aware Python datetime normalized to UTC."""

    return parse_timestamp(validated(_construct_datetime), cs)


def read_instant_calendar(cs: str) -> InstantCalendar:
    """Read ``cs`` as an offset-preserving portable calendar value."""

    return parse_timestamp(validated(_construct_calendar), cs)


def read_instant_timestamp(cs: str) -> InstantTimestamp:
    """Read ``cs`` as a UTC timestamp value preserving parsed nanoseconds."""

    return parse_timestamp(validated(_construct_timestamp), cs)


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
    normalized = value.astimezone(_UTC)
    return InstantDateTime(
        normalized.year,
        normalized.month,
        normalized.day,
        normalized.hour,
        normalized.minute,
        normalized.second,
        normalized.microsecond,
        tzinfo=normalized.tzinfo,
        fold=normalized.fold,
    )


def _offset_timezone(
    offset_sign: int, offset_hours: int, offset_minutes: int
) -> tuple[datetime.timezone, int]:
    total_offset_minutes = offset_sign * ((offset_hours * 60) + offset_minutes)
    return (
        datetime.timezone(datetime.timedelta(minutes=total_offset_minutes)),
        total_offset_minutes,
    )


def _construct_calendar(
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
) -> InstantCalendar:
    timezone, total_offset_minutes = _offset_timezone(
        offset_sign, offset_hours, offset_minutes
    )
    return InstantCalendar(
        datetime=datetime.datetime(
            years,
            months,
            days,
            hours,
            minutes,
            seconds,
            nanoseconds // 1_000,
            tzinfo=timezone,
        ),
        nanoseconds=nanoseconds,
        offset_minutes=total_offset_minutes,
    )


def _construct_timestamp(
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
) -> InstantTimestamp:
    normalized = _construct_datetime(
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
    return InstantTimestamp(
        normalized.year,
        normalized.month,
        normalized.day,
        normalized.hour,
        normalized.minute,
        normalized.second,
        normalized.microsecond,
        tzinfo=normalized.tzinfo,
        fold=normalized.fold,
        nanoseconds=nanoseconds,
    )
