import datetime
from fractions import Fraction

import pytest

from basilisp.lang import instant


def test_parse_timestamp_passes_clojure_compatible_defaults_and_fraction():
    received = []

    result = instant.parse_timestamp(
        lambda *components: received.append(components),
        "2024-02-03T04:05:06.7-07:30",
    )

    assert result is None
    assert received == [(2024, 2, 3, 4, 5, 6, 700_000_000, -1, 7, 30)]
    assert instant.parse_timestamp(lambda *components: components, "2024") == (
        2024,
        1,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )
    assert instant.parse_timestamp(lambda *components: components, "2024-02-03T04") == (
        2024,
        2,
        3,
        4,
        0,
        0,
        0,
        0,
        0,
        0,
    )


def test_parse_timestamp_accepts_utc_and_truncates_long_fractions():
    assert instant.parse_timestamp(lambda *components: components, "2024Z") == (
        2024,
        1,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )
    assert instant.parse_timestamp(
        lambda *components: components, "2024-01-02T03:04:05.123456789123Z"
    ) == (
        2024,
        1,
        2,
        3,
        4,
        5,
        123_456_789,
        0,
        0,
        0,
    )


def test_parse_timestamp_is_grammar_only_for_calendar_fields():
    assert instant.parse_timestamp(lambda *components: components, "2024-99") == (
        2024,
        99,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )
    assert instant.parse_timestamp(
        lambda *components: components, "2024-01-01T00:59:60Z"
    ) == (
        2024,
        1,
        1,
        0,
        59,
        60,
        0,
        0,
        0,
        0,
    )


@pytest.mark.parametrize(
    "value",
    ["", "2024-1", "2024-01-01T", "2024-01-01+01"],
)
def test_parse_timestamp_rejects_non_matching_input(value):
    with pytest.raises(ValueError, match="Unrecognized date/time syntax"):
        instant.parse_timestamp(lambda *components: components, value)


def test_validated_rejects_invalid_calendar_values_and_read_instant_normalizes_utc():
    constructor = instant.validated(tuple)
    with pytest.raises(ValueError, match="day is not valid"):
        instant.parse_timestamp(constructor, "2023-02-29")

    assert instant.read_instant(
        "2024-02-29T01:02:03.123456789+02:30"
    ) == datetime.datetime(2024, 2, 28, 22, 32, 3, 123456, tzinfo=datetime.timezone.utc)
    with pytest.raises(ValueError, match="second"):
        instant.read_instant("2024-01-01T00:00:60Z")
    with pytest.raises(ValueError, match="second"):
        instant.read_instant("2024-01-01T00:59:60Z")


def test_read_instant_exposes_exact_timestamp_seconds():
    value = instant.read_instant("2010-01-01T01:01:01.001-01:01")

    assert isinstance(value, datetime.datetime)
    assert value == datetime.datetime(
        2010, 1, 1, 2, 2, 1, 1000, tzinfo=datetime.timezone.utc
    )
    assert value.timestamp() == Fraction(1262311321001, 1000)
    assert value.timestamp() * 1000 == 1262311321001


def test_epoch_millis_uses_exact_integer_arithmetic():
    assert (
        instant.epoch_millis(
            datetime.datetime(2010, 1, 1, 2, 2, 1, 1000, tzinfo=datetime.timezone.utc)
        )
        == 1262311321001
    )
    assert (
        instant.epoch_millis(
            datetime.datetime(
                1969, 12, 31, 23, 59, 59, 999500, tzinfo=datetime.timezone.utc
            )
        )
        == -1
    )
