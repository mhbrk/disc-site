import asyncio
from typing import List

import pytest
import pytest_asyncio
from pydantic import BaseModel

from breba_app.events.bus import EventBus, HandleContext, Subscription


# Test Event Models
class UserCreated(BaseModel):
    user_id: int
    username: str


class UserDeleted(BaseModel):
    user_id: int


class OrderPlaced(BaseModel):
    order_id: int
    amount: float


# Test Consumer Implementation
class TestConsumer:
    def __init__(self):
        self.handled_events: List[BaseModel] = []
        self.contexts: List[HandleContext] = []
        self.call_count = 0

    async def handle(self, ctx: HandleContext, event: BaseModel) -> None:
        self.call_count += 1
        self.handled_events.append(event)
        self.contexts.append(ctx)


class AsyncTestConsumer:
    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.handled_events: List[BaseModel] = []

    async def handle(self, ctx: HandleContext, event: BaseModel) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        self.handled_events.append(event)


class FailingConsumer:
    def __init__(self, exception: Exception = ValueError("Test error")):
        self.exception = exception
        self.call_count = 0

    async def handle(self, ctx: HandleContext, event: BaseModel) -> None:
        self.call_count += 1
        raise self.exception


class UnsubscribingConsumer:
    def __init__(self):
        self.call_count = 0

    async def handle(self, ctx: HandleContext, event: BaseModel) -> None:
        self.call_count += 1
        await ctx.unsubscribe_self()


# Fixtures
@pytest.fixture
def event_bus():
    return EventBus()


@pytest_asyncio.fixture
async def event_bus_with_cleanup():
    bus = EventBus()
    yield bus
    await bus.close()


# Basic Subscription Tests
@pytest.mark.asyncio
async def test_subscribe_returns_subscription(event_bus):
    consumer = TestConsumer()
    subscription = await event_bus.subscribe(UserCreated, consumer)

    assert isinstance(subscription, Subscription)
    assert subscription.event_type == UserCreated
    assert subscription.id > 0


@pytest.mark.asyncio
async def test_subscribe_multiple_consumers_same_event(event_bus):
    consumer1 = TestConsumer()
    consumer2 = TestConsumer()

    sub1 = await event_bus.subscribe(UserCreated, consumer1)
    sub2 = await event_bus.subscribe(UserCreated, consumer2)

    assert sub1.id != sub2.id
    assert sub1.event_type == sub2.event_type


@pytest.mark.asyncio
async def test_subscribe_different_event_types(event_bus):
    consumer1 = TestConsumer()
    consumer2 = TestConsumer()

    sub1 = await event_bus.subscribe(UserCreated, consumer1)
    sub2 = await event_bus.subscribe(OrderPlaced, consumer2)

    assert sub1.event_type != sub2.event_type


# Unsubscribe Tests
@pytest.mark.asyncio
async def test_unsubscribe_success(event_bus):
    consumer = TestConsumer()
    subscription = await event_bus.subscribe(UserCreated, consumer)

    result = await event_bus.unsubscribe(subscription)

    assert result is True


@pytest.mark.asyncio
async def test_unsubscribe_nonexistent_subscription(event_bus):
    fake_subscription = Subscription(id=999, event_type=UserCreated)

    result = await event_bus.unsubscribe(fake_subscription)

    assert result is False


@pytest.mark.asyncio
async def test_unsubscribe_twice(event_bus):
    consumer = TestConsumer()
    subscription = await event_bus.subscribe(UserCreated, consumer)

    result1 = await event_bus.unsubscribe(subscription)
    result2 = await event_bus.unsubscribe(subscription)

    assert result1 is True
    assert result2 is False


# Emit Tests (wait=False)
@pytest.mark.asyncio
async def test_emit_no_subscribers(event_bus_with_cleanup):
    event = UserCreated(user_id=1, username="alice")

    # Should not raise
    await event_bus_with_cleanup.emit(event, wait=False)
    await asyncio.sleep(0.01)  # Let background tasks run


@pytest.mark.asyncio
async def test_emit_single_subscriber(event_bus_with_cleanup):
    consumer = TestConsumer()
    await event_bus_with_cleanup.subscribe(UserCreated, consumer)

    event = UserCreated(user_id=1, username="alice")
    await event_bus_with_cleanup.emit(event, wait=False)

    # Wait for background task
    await asyncio.sleep(0.01)

    assert consumer.call_count == 1
    assert consumer.handled_events[0] == event


@pytest.mark.asyncio
async def test_emit_multiple_subscribers(event_bus_with_cleanup):
    consumer1 = TestConsumer()
    consumer2 = TestConsumer()
    consumer3 = TestConsumer()

    await event_bus_with_cleanup.subscribe(UserCreated, consumer1)
    await event_bus_with_cleanup.subscribe(UserCreated, consumer2)
    await event_bus_with_cleanup.subscribe(UserCreated, consumer3)

    event = UserCreated(user_id=1, username="alice")
    await event_bus_with_cleanup.emit(event, wait=False)

    await asyncio.sleep(0.01)

    assert consumer1.call_count == 1
    assert consumer2.call_count == 1
    assert consumer3.call_count == 1


@pytest.mark.asyncio
async def test_emit_only_matching_event_type(event_bus_with_cleanup):
    user_consumer = TestConsumer()
    order_consumer = TestConsumer()

    await event_bus_with_cleanup.subscribe(UserCreated, user_consumer)
    await event_bus_with_cleanup.subscribe(OrderPlaced, order_consumer)

    event = UserCreated(user_id=1, username="alice")
    await event_bus_with_cleanup.emit(event, wait=False)

    await asyncio.sleep(0.01)

    assert user_consumer.call_count == 1
    assert order_consumer.call_count == 0


# Emit Tests (wait=True)
@pytest.mark.asyncio
async def test_emit_wait_true_single_subscriber(event_bus):
    consumer = TestConsumer()
    await event_bus.subscribe(UserCreated, consumer)

    event = UserCreated(user_id=1, username="alice")
    await event_bus.emit(event, wait=True)

    assert consumer.call_count == 1
    assert consumer.handled_events[0] == event


@pytest.mark.asyncio
async def test_emit_wait_true_multiple_subscribers(event_bus):
    consumer1 = AsyncTestConsumer(delay=0.01)
    consumer2 = AsyncTestConsumer(delay=0.02)

    await event_bus.subscribe(UserCreated, consumer1)
    await event_bus.subscribe(UserCreated, consumer2)

    event = UserCreated(user_id=1, username="alice")
    await event_bus.emit(event, wait=True)

    # Should wait for all consumers
    assert len(consumer1.handled_events) == 1
    assert len(consumer2.handled_events) == 1


@pytest.mark.asyncio
async def test_emit_wait_true_no_subscribers(event_bus):
    event = UserCreated(user_id=1, username="alice")

    # Should not raise
    await event_bus.emit(event, wait=True)


# HandleContext Tests
@pytest.mark.asyncio
async def test_handle_context_properties(event_bus_with_cleanup):
    consumer = TestConsumer()
    subscription = await event_bus_with_cleanup.subscribe(UserCreated, consumer)

    event = UserCreated(user_id=1, username="alice")
    await event_bus_with_cleanup.emit(event, wait=True)

    ctx = consumer.contexts[0]
    assert ctx.subscription == subscription
    assert ctx.event == event


@pytest.mark.asyncio
async def test_handle_context_unsubscribe_self(event_bus_with_cleanup):
    consumer = UnsubscribingConsumer()
    await event_bus_with_cleanup.subscribe(UserCreated, consumer)

    # Emit twice
    event1 = UserCreated(user_id=1, username="alice")
    event2 = UserCreated(user_id=2, username="bob")

    await event_bus_with_cleanup.emit(event1, wait=True)
    await event_bus_with_cleanup.emit(event2, wait=True)

    # Should only be called once (unsubscribed after first)
    assert consumer.call_count == 1


@pytest.mark.asyncio
async def test_handle_context_emit(event_bus_with_cleanup):
    """Test that consumers can emit events via HandleContext"""
    received_events = []

    class EmittingConsumer:
        async def handle(self, ctx: HandleContext, event: UserCreated) -> None:
            # Emit a different event
            await ctx.emit(UserDeleted(user_id=event.user_id), wait=True)

    class ListeningConsumer:
        async def handle(self, ctx: HandleContext, event: UserDeleted) -> None:
            received_events.append(event)

    await event_bus_with_cleanup.subscribe(UserCreated, EmittingConsumer())
    await event_bus_with_cleanup.subscribe(UserDeleted, ListeningConsumer())

    event = UserCreated(user_id=1, username="alice")
    await event_bus_with_cleanup.emit(event, wait=True)

    assert len(received_events) == 1
    assert received_events[0].user_id == 1


# Error Handling Tests
@pytest.mark.asyncio
async def test_consumer_exception_does_not_crash_bus(event_bus_with_cleanup, caplog):
    failing = FailingConsumer()
    success = TestConsumer()

    await event_bus_with_cleanup.subscribe(UserCreated, failing)
    await event_bus_with_cleanup.subscribe(UserCreated, success)

    event = UserCreated(user_id=1, username="alice")
    await event_bus_with_cleanup.emit(event, wait=True)

    # Failing consumer should have been called
    assert failing.call_count == 1
    # Success consumer should still work
    assert success.call_count == 1
    assert success.handled_events[0] == event


@pytest.mark.asyncio
async def test_consumer_exception_logged(event_bus_with_cleanup, caplog):
    import logging
    caplog.set_level(logging.ERROR)

    failing = FailingConsumer(ValueError("Custom error"))
    await event_bus_with_cleanup.subscribe(UserCreated, failing)

    event = UserCreated(user_id=1, username="alice")
    await event_bus_with_cleanup.emit(event, wait=True)

    assert "Consumer failed" in caplog.text
    assert "Custom error" in caplog.text


# Concurrency Tests
@pytest.mark.asyncio
async def test_concurrent_subscriptions(event_bus):
    consumers = [TestConsumer() for _ in range(10)]

    async def subscribe_consumer(c):
        return await event_bus.subscribe(UserCreated, c)

    subscriptions = await asyncio.gather(*[subscribe_consumer(c) for c in consumers])

    # All should have unique IDs
    ids = [s.id for s in subscriptions]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_concurrent_emissions(event_bus_with_cleanup):
    consumer = TestConsumer()
    await event_bus_with_cleanup.subscribe(UserCreated, consumer)

    events = [UserCreated(user_id=i, username=f"user{i}") for i in range(10)]

    await asyncio.gather(*[
        event_bus_with_cleanup.emit(e, wait=True) for e in events
    ])

    assert consumer.call_count == 10


@pytest.mark.asyncio
async def test_unsubscribe_during_emission(event_bus_with_cleanup):
    """Test that unsubscribing during emission doesn't break iteration"""
    consumer1 = TestConsumer()
    consumer2 = UnsubscribingConsumer()
    consumer3 = TestConsumer()

    await event_bus_with_cleanup.subscribe(UserCreated, consumer1)
    await event_bus_with_cleanup.subscribe(UserCreated, consumer2)
    await event_bus_with_cleanup.subscribe(UserCreated, consumer3)

    event = UserCreated(user_id=1, username="alice")
    await event_bus_with_cleanup.emit(event, wait=True)

    # All should have been called
    assert consumer1.call_count == 1
    assert consumer2.call_count == 1
    assert consumer3.call_count == 1


# Close/Cleanup Tests
@pytest.mark.asyncio
async def test_close_cancels_background_tasks(event_bus):
    consumer = AsyncTestConsumer(delay=1.0)  # Long delay
    await event_bus.subscribe(UserCreated, consumer)

    event = UserCreated(user_id=1, username="alice")
    await event_bus.emit(event, wait=False)

    # Close before task finishes
    await asyncio.sleep(0.01)
    await event_bus.close()

    # Task should be cancelled, consumer might not have finished
    assert len(event_bus._bg_tasks) == 0


@pytest.mark.asyncio
async def test_close_idempotent():
    """Calling close multiple times should be safe"""
    bus = EventBus()
    await bus.close()
    await bus.close()  # Should not raise


@pytest.mark.asyncio
async def test_background_tasks_cleaned_up(event_bus_with_cleanup):
    consumer = TestConsumer()
    await event_bus_with_cleanup.subscribe(UserCreated, consumer)

    event = UserCreated(user_id=1, username="alice")
    await event_bus_with_cleanup.emit(event, wait=False)

    # Wait for task to complete
    await asyncio.sleep(0.02)

    # Background tasks should auto-cleanup
    assert len(event_bus_with_cleanup._bg_tasks) == 0


# Edge Cases
@pytest.mark.asyncio
async def test_emit_with_no_event_type_match(event_bus_with_cleanup):
    consumer = TestConsumer()
    await event_bus_with_cleanup.subscribe(UserCreated, consumer)

    # Emit different event type
    event = OrderPlaced(order_id=1, amount=99.99)
    await event_bus_with_cleanup.emit(event, wait=False)

    await asyncio.sleep(0.01)

    assert consumer.call_count == 0


@pytest.mark.asyncio
async def test_subscription_id_increments(event_bus):
    consumer = TestConsumer()

    sub1 = await event_bus.subscribe(UserCreated, consumer)
    sub2 = await event_bus.subscribe(UserCreated, consumer)
    sub3 = await event_bus.subscribe(OrderPlaced, consumer)

    assert sub2.id == sub1.id + 1
    assert sub3.id == sub2.id + 1


@pytest.mark.asyncio
async def test_multiple_events_to_same_consumer(event_bus_with_cleanup):
    consumer = TestConsumer()
    await event_bus_with_cleanup.subscribe(UserCreated, consumer)

    events = [
        UserCreated(user_id=1, username="alice"),
        UserCreated(user_id=2, username="bob"),
        UserCreated(user_id=3, username="charlie"),
    ]

    for event in events:
        await event_bus_with_cleanup.emit(event, wait=True)

    assert consumer.call_count == 3
    assert consumer.handled_events == events
