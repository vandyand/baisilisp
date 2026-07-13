import asyncio

import pytest

from basilisp.concurrent_channel import (
    DEFAULT_PORT,
    Channel,
    alts,
    pipe,
    pipeline,
    timeout,
)


def run(coro):
    return asyncio.run(coro)


def map_xform(function):
    """Small Python transducer fixture, independent of Basilisp core loading."""

    def xform(reducing_function):
        def reducing(*args):
            if not args:
                return reducing_function()
            if len(args) == 1:
                return reducing_function(args[0])
            result, value = args
            return reducing_function(result, function(value))

        return reducing

    return xform


def mapcat_xform(function):
    def xform(reducing_function):
        def reducing(*args):
            if not args:
                return reducing_function()
            if len(args) == 1:
                return reducing_function(args[0])
            result, value = args
            for emitted in function(value):
                result = reducing_function(result, emitted)
            return result

        return reducing

    return xform


def test_rendezvous_channel_matches_put_and_take():
    async def scenario():
        channel = Channel()
        putter = asyncio.create_task(channel.put("value"))
        await asyncio.sleep(0)
        assert not putter.done()
        assert await channel.take() == "value"
        assert await putter is True

    run(scenario())


def test_fixed_channel_applies_backpressure_and_preserves_fifo_order():
    async def scenario():
        channel = Channel(2)
        assert await channel.put("first") is True
        assert await channel.put("second") is True
        blocked = asyncio.create_task(channel.put("third"))
        await asyncio.sleep(0)
        assert not blocked.done()
        assert await channel.take() == "first"
        assert await blocked is True
        assert [await channel.take(), await channel.take()] == ["second", "third"]

    run(scenario())


@pytest.mark.parametrize(
    ("policy", "expected"),
    [("sliding", ["second", "third"]), ("dropping", ["first", "second"])],
)
def test_nonblocking_buffer_policies(policy, expected):
    async def scenario():
        channel = Channel(2, policy=policy)
        for value in ("first", "second", "third"):
            assert await channel.put(value) is True
        assert [await channel.take(), await channel.take()] == expected

    run(scenario())


def test_close_wakes_blocked_waiters_and_retains_buffered_values():
    async def scenario():
        channel = Channel(1)
        assert await channel.put("buffered") is True
        blocked_put = asyncio.create_task(channel.put("blocked"))
        await asyncio.sleep(0)
        channel.close()
        assert await blocked_put is False
        assert await channel.take() == "buffered"
        assert await channel.take() is None

    run(scenario())


def test_cancelled_waiters_are_removed_before_later_matches():
    async def scenario():
        channel = Channel()
        cancelled_take = asyncio.create_task(channel.take())
        await asyncio.sleep(0)
        cancelled_take.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled_take

        putter = asyncio.create_task(channel.put("value"))
        await asyncio.sleep(0)
        assert await channel.take() == "value"
        assert await putter is True

    run(scenario())


def test_channel_cannot_be_shared_across_event_loops():
    channel = Channel(1)

    run(channel.put("value"))

    with pytest.raises(RuntimeError, match="cannot be shared"):
        run(channel.take())


def test_alts_selects_ready_take_by_priority_and_returns_default_without_waiting():
    async def scenario():
        first = Channel(1)
        second = Channel(1)
        assert await first.put("first")
        assert await second.put("second")

        assert await alts([second, first], priority=True) == ("second", second)
        assert await alts([first], default="fallback") == ("first", first)
        assert await alts([Channel()], default="fallback") == ("fallback", DEFAULT_PORT)

    run(scenario())


def test_alts_selects_puts_and_only_completes_one_operation():
    async def scenario():
        first = Channel()
        second = Channel()
        selector = asyncio.create_task(alts([(first, "first"), (second, "second")]))
        await asyncio.sleep(0)

        assert await second.take() == "second"
        assert await selector == (True, second)
        assert first.poll() is None

    run(scenario())


def test_alts_cancellation_removes_every_registered_waiter():
    async def scenario():
        first = Channel()
        second = Channel()
        selector = asyncio.create_task(alts([first, second]))
        await asyncio.sleep(0)
        selector.cancel()
        with pytest.raises(asyncio.CancelledError):
            await selector

        putter = asyncio.create_task(first.put("value"))
        await asyncio.sleep(0)
        assert await first.take() == "value"
        assert await putter is True
        assert second.poll() is None

    run(scenario())


def test_alts_handles_closed_channels_and_timeout_closes_once():
    async def scenario():
        channel = Channel()
        channel.close()
        assert await alts([channel]) == (None, channel)

        timer = timeout(1)
        assert await timer.take() is None
        assert timer.closed

    run(scenario())


def test_timeout_cancelled_by_early_close_does_not_leave_a_live_timer():
    async def scenario():
        timer = timeout(1000)
        timer.close()
        assert timer.closed
        assert timer.timer_cancelled

    run(scenario())

    with pytest.raises(ValueError, match="non-negative"):
        timeout(-1)


def test_alts_stress_never_completes_more_than_one_competing_put():
    async def scenario():
        for index in range(100):
            first = Channel()
            second = Channel()
            selector = asyncio.create_task(alts([first, second]))
            await asyncio.sleep(0)
            first_put = asyncio.create_task(first.put(("first", index)))
            second_put = asyncio.create_task(second.put(("second", index)))
            await asyncio.sleep(0)

            value, selected = await selector
            assert value in (("first", index), ("second", index))
            completed = [put for put in (first_put, second_put) if put.done()]
            assert len(completed) == 1
            assert await completed[0] is True
            assert (selected is first) == (completed[0] is first_put)

            for put in (first_put, second_put):
                if not put.done():
                    put.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await put
            first.close()
            second.close()

    run(scenario())


def test_alts_close_races_and_timers_leave_no_second_winner():
    async def scenario():
        for index in range(100):
            first = Channel()
            second = Channel()
            selector = asyncio.create_task(alts([first, second]))
            await asyncio.sleep(0)

            closing_order = (first, second) if index % 2 else (second, first)
            closing_order[0].close()
            closing_order[1].close()
            assert await selector == (None, closing_order[0])
            assert first.poll() is None
            assert second.poll() is None

        never = Channel()
        timer = timeout(1)
        assert await alts([never, timer]) == (None, timer)

    run(scenario())


def test_pipe_forwards_values_and_has_explicit_output_ownership():
    async def scenario():
        source = Channel(2)
        destination = Channel(2)
        assert await source.put("first")
        assert await source.put("second")
        source.close()

        task = pipe(source, destination)
        assert [await destination.take(), await destination.take()] == [
            "first",
            "second",
        ]
        assert await task is None
        assert destination.closed

        source = Channel(1)
        destination = Channel(1)
        assert await source.put("owned")
        source.close()
        task = pipe(source, destination, close_output=False)
        assert await destination.take() == "owned"
        assert await task is None
        assert not destination.closed

    run(scenario())


def test_pipeline_retains_order_supports_fanout_and_closes_after_drain():
    async def scenario():
        source = Channel(4)
        destination = Channel(8)
        for value in range(4):
            assert await source.put(value)
        source.close()

        def deliberately_out_of_order(value):
            import time

            time.sleep((3 - value) * 0.01)
            return (value, value + 10)

        task = pipeline(4, source, destination, mapcat_xform(deliberately_out_of_order))
        assert [await destination.take() for _ in range(8)] == [
            0,
            10,
            1,
            11,
            2,
            12,
            3,
            13,
        ]
        assert await task is None
        assert destination.closed
        assert await destination.take() is None

    run(scenario())


def test_pipeline_handler_and_closed_output_stop_admission():
    async def scenario():
        source = Channel(3)
        destination = Channel(3)
        for value in range(3):
            assert await source.put(value)
        source.close()

        def fail_on_one(value):
            if value == 1:
                raise RuntimeError("bad input")
            return value

        task = pipeline(
            2,
            source,
            destination,
            map_xform(fail_on_one),
            error_handler=lambda error, value: [f"{type(error).__name__}:{value}"],
        )
        assert [await destination.take() for _ in range(3)] == [0, "RuntimeError:1", 2]
        assert await task is None

        source = Channel(2)
        destination = Channel(1)
        assert await source.put("first")
        assert await source.put("second")
        destination.close()
        task = pipeline(1, source, destination, map_xform(lambda value: value))
        assert await task is None
        assert await source.take() == "second"

    run(scenario())


@pytest.mark.parametrize("parallelism", [0, -1, True, 1.5])
def test_pipeline_validates_parallelism(parallelism):
    async def scenario():
        with pytest.raises((TypeError, ValueError), match="positive integer"):
            pipeline(parallelism, Channel(), Channel(), map_xform(lambda value: value))

    run(scenario())
