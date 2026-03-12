from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Subscription[E: BaseModel]:
    """
    Opaque token used for unsubscribing.
    """
    id: str
    event_type: type[E]


class HandleContext[E: BaseModel]:
    """
    Passed to consumers so they can unsubscribe themselves (and optionally emit).
    """
    __slots__ = ("_bus", "_subscription", "_event")

    def __init__(self, *, bus: EventBus, subscription: Subscription[E], event: E) -> None:
        self._bus = bus
        self._subscription = subscription
        self._event = event

    @property
    def subscription(self) -> Subscription[E]:
        return self._subscription

    @property
    def event(self) -> E:
        return self._event

    async def unsubscribe_self(self) -> bool:
        return await self._bus.unsubscribe(self._subscription)

    async def emit(self, event: BaseModel, *, wait: bool = False) -> None:
        await self._bus.emit(event, wait=wait)


class Consumer[E: BaseModel](Protocol):
    """
    ESB-ish consumer interface.
    """

    id: str | None = None

    async def handle(self, ctx: HandleContext[E], event: E) -> None: ...


class EventBus:
    """
    Minimal async pub/sub bus with consumer objects.

    - subscribe(event_type, consumer) -> Subscription token
    - unsubscribe(token) -> bool
    - emit(event) schedules consumer.handle(...) in separate tasks
    - emit(..., wait=True) awaits all using TaskGroup (structured concurrency)
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._next_id = 1

        # event_type -> subscription_id -> consumer
        self._consumers: dict[type[BaseModel], dict[str, Consumer[BaseModel]]] = {}

        # Background tasks for wait=False mode
        self._bg_tasks: set[asyncio.Task[None]] = set()

    async def subscribe[E: BaseModel](
            self, event_type: type[E], consumer: Consumer[E]
    ) -> Subscription[E]:
        async with self._lock:
            if consumer.id is None:
                consumer.id = str(uuid.uuid4())
            bucket = self._consumers.setdefault(event_type, {})
            bucket[consumer.id] = consumer
        return Subscription(id=consumer.id, event_type=event_type)

    async def unsubscribe[E: BaseModel](self, subscription: Subscription[E]) -> bool:
        async with self._lock:
            bucket = self._consumers.get(subscription.event_type)
            if not bucket:
                return False
            removed = bucket.pop(subscription.id, None) is not None
            if not bucket:
                self._consumers.pop(subscription.event_type, None)
        return removed

    async def emit[E: BaseModel](self, event: E, *, wait: bool = False) -> None:
        event_type: type[E] = type(event)

        # Snapshot subscriptions so unsubscribes during handling are safe.
        async with self._lock:
            bucket = self._consumers.get(event_type, {})
            items = list(bucket.items())

        if not items:
            return

        if wait:
            async with asyncio.TaskGroup() as tg:
                for sub_id, consumer in items:
                    sub: Subscription[E] = Subscription(id=sub_id, event_type=event_type)
                    ctx = HandleContext(bus=self, subscription=sub, event=event)
                    tg.create_task(self._run_consumer(consumer, ctx, event))
            return

        for sub_id, consumer in items:
            sub = Subscription(id=sub_id, event_type=event_type)
            ctx = HandleContext(bus=self, subscription=sub, event=event)
            task = asyncio.create_task(self._run_consumer(consumer, ctx, event))
            self._bg_tasks.add(task)
            task.add_done_callback(self._bg_tasks.discard)

    async def _run_consumer(
            self, consumer: Consumer[BaseModel], ctx: HandleContext, event: BaseModel
    ) -> None:
        try:
            await consumer.handle(ctx, event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Consumer failed. event_type=%s consumer=%r subscription=%s",
                type(event).__name__,
                consumer,
                ctx.subscription,
            )

    async def close(self) -> None:
        """
        Optional graceful shutdown for wait=False emissions.
        """
        tasks = list(self._bg_tasks)
        for t in tasks:
            t.cancel()
        if tasks:
            with contextlib.suppress(Exception):
                await asyncio.gather(*tasks, return_exceptions=True)
        self._bg_tasks.clear()


event_bus = EventBus()
