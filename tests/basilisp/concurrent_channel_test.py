import asyncio

import pytest

from basilisp.concurrent_channel import Channel


def run(coro):
    return asyncio.run(coro)


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
