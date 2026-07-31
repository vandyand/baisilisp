import asyncio
import random
import threading

import pytest

from basilisp.concurrent_channel import (
    DEFAULT_PORT,
    Channel,
    PromiseChannel,
    alts,
    blocking_alts,
    blocking_put,
    blocking_take,
    pipe,
    pipeline,
    pipeline_async,
    submit_coroutine,
    timeout,
    try_alts,
)
from basilisp.lang.reduced import Reduced


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


def filter_xform(predicate):
    def xform(reducing_function):
        def reducing(*args):
            if not args:
                return reducing_function()
            if len(args) == 1:
                return reducing_function(args[0])
            result, value = args
            if predicate(value):
                return reducing_function(result, value)
            return result

        return reducing

    return xform


def take_xform(limit):
    def xform(reducing_function):
        remaining = limit

        def reducing(*args):
            nonlocal remaining
            if not args:
                return reducing_function()
            if len(args) == 1:
                return reducing_function(args[0])
            result, value = args
            if remaining <= 0:
                return Reduced(result)
            remaining -= 1
            result = reducing_function(result, value)
            return Reduced(result) if remaining == 0 else result

        return reducing

    return xform


def partition_all_xform(size):
    def xform(reducing_function):
        partition = []

        def reducing(*args):
            nonlocal partition
            if not args:
                return reducing_function()
            if len(args) == 1:
                result = args[0]
                if partition:
                    result = reducing_function(result, tuple(partition))
                    partition = []
                return reducing_function(result)
            result, value = args
            partition.append(value)
            if len(partition) == size:
                result = reducing_function(result, tuple(partition))
                partition = []
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


def test_transducing_channel_maps_filters_fans_out_and_flushes_on_close():
    async def scenario():
        mapped = Channel(4, xform=map_xform(lambda value: value + 1))
        assert await mapped.put(1)
        assert await mapped.put(2)
        mapped.close()
        assert [await mapped.take(), await mapped.take(), await mapped.take()] == [
            2,
            3,
            None,
        ]

        filtered = Channel(4, xform=filter_xform(lambda value: value % 2 == 0))
        for value in range(5):
            assert await filtered.put(value)
        filtered.close()
        assert [
            await filtered.take(),
            await filtered.take(),
            await filtered.take(),
        ] == [
            0,
            2,
            4,
        ]
        assert await filtered.take() is None

        fanned = Channel(8, xform=mapcat_xform(lambda value: (value, value * 10)))
        assert await fanned.put(1)
        assert await fanned.put(2)
        fanned.close()
        assert [await fanned.take() for _ in range(5)] == [1, 10, 2, 20, None]

        partitioned = Channel(4, xform=partition_all_xform(2))
        for value in (1, 2, 3):
            assert await partitioned.put(value)
        partitioned.close()
        assert [await partitioned.take(), await partitioned.take()] == [(1, 2), (3,)]
        assert await partitioned.take() is None

    run(scenario())


def test_promise_channel_realizes_once_and_repeats_value():
    async def scenario():
        channel = PromiseChannel()
        assert channel.offer("first") is True
        assert channel.offer("ignored") is True
        assert channel.poll() == "first"
        assert channel.poll() == "first"
        assert await channel.put("also-ignored") is True
        assert [await channel.take(), await channel.take()] == ["first", "first"]

    run(scenario())


def test_promise_channel_close_empty_and_transducer_mapping():
    async def scenario():
        closed = PromiseChannel()
        closed.close()
        assert closed.offer("late") is False
        assert closed.poll() is None
        assert await closed.put("late") is False
        assert await closed.take() is None

        transformed = PromiseChannel(xform=map_xform(lambda value: value + 1))
        assert await transformed.put(1) is True
        assert await transformed.put(2) is True
        assert [await transformed.take(), await transformed.take()] == [2, 2]

    run(scenario())


def test_promise_channel_participates_in_alts_after_realization_and_close():
    async def scenario():
        realized = PromiseChannel()
        empty_closed = PromiseChannel()
        assert await realized.put("ready") is True
        empty_closed.close()
        assert await alts([realized], priority=True) == ("ready", realized)
        assert await alts([empty_closed], priority=True) == (None, empty_closed)

    run(scenario())


def test_transducing_channel_completion_error_handler_and_nil_rejection():
    async def scenario():
        limited = Channel(4, xform=take_xform(2))
        assert await limited.put("first") is True
        assert await limited.put("second") is True
        assert await limited.put("third") is False
        assert [await limited.take(), await limited.take(), await limited.take()] == [
            "first",
            "second",
            None,
        ]

        def fail_on_even(value):
            if value % 2 == 0:
                raise RuntimeError(f"bad:{value}")
            return value

        handled = Channel(
            4,
            xform=map_xform(fail_on_even),
            error_handler=lambda error: f"{type(error).__name__}:{error}",
        )
        for value in (1, 2, 3):
            assert await handled.put(value)
        handled.close()
        assert [await handled.take() for _ in range(4)] == [
            1,
            "RuntimeError:bad:2",
            3,
            None,
        ]

        dropped = Channel(
            4,
            xform=map_xform(fail_on_even),
            error_handler=lambda _error: None,
        )
        for value in (1, 2, 3):
            assert await dropped.put(value)
        dropped.close()
        assert [await dropped.take(), await dropped.take(), await dropped.take()] == [
            1,
            3,
            None,
        ]

        nil_output = Channel(1, xform=map_xform(lambda _value: None))
        with pytest.raises(ValueError, match="nil values"):
            await nil_output.put("input")

    run(scenario())


def test_transducing_channel_respects_output_backpressure_before_input_admission():
    async def scenario():
        channel = Channel(1, xform=partition_all_xform(2))
        assert await channel.put(1)
        assert await channel.put(2)

        blocked = asyncio.create_task(channel.put(3))
        await asyncio.sleep(0)
        assert not blocked.done()

        assert await channel.take() == (1, 2)
        assert await blocked is True
        channel.close()
        assert await channel.take() == (3,)
        assert await channel.take() is None

    run(scenario())


def test_transducing_channel_offer_is_atomic_around_backpressure_and_fanout():
    async def scenario():
        partitioned = Channel(1, xform=partition_all_xform(2))
        assert partitioned.offer(1) is True
        assert partitioned.offer(2) is True
        assert partitioned.offer(3) is False
        partitioned.close()
        assert await partitioned.take() == (1, 2)
        assert await partitioned.take() is None

        fanned = Channel(1, xform=mapcat_xform(lambda value: (value, value * 10)))
        assert fanned.offer(1) is True
        assert await fanned.take() == 1
        assert await fanned.take() == 10

    run(scenario())


def test_transducing_channel_seeded_stress_matches_reference_model():
    async def scenario():
        rng = random.Random(8675309)
        for _ in range(50):
            values = [rng.randrange(20) for _ in range(25)]
            channel = Channel(
                len(values) * 2,
                xform=mapcat_xform(
                    lambda value: (value, value + 100) if value % 3 else ()
                ),
            )
            for value in values:
                assert await channel.put(value)
            channel.close()
            expected = [
                item for value in values if value % 3 for item in (value, value + 100)
            ]
            observed = [await channel.take() for _ in expected]
            assert observed == expected
            assert await channel.take() is None

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


def test_blocking_put_take_and_alts_on_unbound_channels():
    channel = Channel(1)
    assert blocking_put(channel, "value") is True
    assert blocking_take(channel) == "value"

    first = Channel(1)
    second = Channel(1)
    assert blocking_put(first, "first")
    assert blocking_put(second, "second")
    assert blocking_alts([second, first], priority=True) == ("second", second)
    assert blocking_alts([Channel()], default="fallback") == (
        "fallback",
        DEFAULT_PORT,
    )


def test_blocking_put_can_cross_into_an_owner_event_loop():
    async def scenario():
        channel = Channel()
        assert channel.offer("pre-bind") is False
        results = []
        worker = threading.Thread(
            target=lambda: results.append(blocking_put(channel, "value"))
        )
        worker.start()
        assert await channel.take() == "value"
        await asyncio.sleep(0)
        worker.join(timeout=2)
        assert results == [True]

    run(scenario())


def test_blocking_operations_reject_the_owning_event_loop():
    async def scenario():
        channel = Channel(1)
        assert await channel.put("value")
        with pytest.raises(RuntimeError, match="owning event loop"):
            blocking_take(channel)
        with pytest.raises(RuntimeError, match="owning event loop"):
            blocking_put(channel, "another")
        with pytest.raises(RuntimeError, match="owning event loop"):
            blocking_alts([channel])

    run(scenario())


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


def test_try_alts_selects_immediate_operations_without_enqueuing():
    async def scenario():
        first = Channel(1)
        second = Channel(1)
        second.offer("second")

        assert try_alts([first, second], priority=True) == (True, ("second", second))
        assert try_alts([first], default="fallback") == (
            True,
            ("fallback", DEFAULT_PORT),
        )
        assert try_alts([first]) == (False, None)
        assert first.offer("after-try") is True
        assert first.poll() == "after-try"

        target = Channel(1)
        assert try_alts([(target, "written")], priority=True) == (
            True,
            (True, target),
        )
        assert target.poll() == "written"

        with pytest.raises(ValueError, match="nil"):
            try_alts([(target, None)])

    run(scenario())


def test_submit_coroutine_runs_without_current_event_loop():
    async def value():
        return "done"

    future = submit_coroutine(value())
    assert future.result(timeout=2) == "done"


def test_submit_coroutine_uses_current_event_loop_when_available():
    async def scenario():
        async def value():
            return "done"

        task = submit_coroutine(value())
        assert isinstance(task, asyncio.Task)
        assert await task == "done"

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


def test_pipeline_async_retains_order_with_out_of_order_callbacks():
    async def scenario():
        source = Channel(4)
        destination = Channel(8)
        for value in range(4):
            assert await source.put(value)
        source.close()

        async def emit(value, output):
            await asyncio.sleep((3 - value) * 0.01)
            assert await output.put(value)
            assert await output.put(value + 10)
            output.close()

        def async_function(value, output):
            return asyncio.create_task(emit(value, output))

        task = pipeline_async(4, source, destination, async_function)
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


def test_pipeline_async_close_output_false_and_closed_destination():
    async def scenario():
        async def emit(value, output):
            assert await output.put(value)
            output.close()

        source = Channel(1)
        destination = Channel(1)
        assert await source.put("owned")
        source.close()
        task = pipeline_async(1, source, destination, emit, close_output=False)
        assert await destination.take() == "owned"
        assert await task is None
        assert not destination.closed

        source = Channel(2)
        destination = Channel(1)
        assert await source.put("first")
        assert await source.put("second")
        destination.close()
        task = pipeline_async(1, source, destination, emit)
        assert await task is None
        assert await source.take() == "second"

    run(scenario())


def test_pipeline_async_seeded_stress_preserves_order_and_no_duplicates():
    async def scenario():
        rng = random.Random(1729)
        for _ in range(20):
            values = list(range(12))
            delays = {value: rng.random() / 200 for value in values}
            source = Channel(len(values))
            destination = Channel(len(values) * 2)
            for value in values:
                assert await source.put(value)
            source.close()

            async def emit(value, output):
                await asyncio.sleep(delays[value])
                assert await output.put(value)
                assert await output.put(("done", value))
                output.close()

            task = pipeline_async(3, source, destination, emit)
            expected = [item for value in values for item in (value, ("done", value))]
            observed = [await destination.take() for _ in expected]
            assert observed == expected
            assert await task is None
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


@pytest.mark.parametrize("parallelism", [0, -1, True, 1.5])
def test_pipeline_async_validates_parallelism(parallelism):
    async def scenario():
        with pytest.raises((TypeError, ValueError), match="positive integer"):
            pipeline_async(parallelism, Channel(), Channel(), lambda _value, _out: None)

    run(scenario())
