import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar

import chainlit as cl

THINKING = "Thinking..."
DONE = "Done"


class Task:
    def __init__(self):
        self.msg = cl.Message(content=THINKING)
        self.action_queue = asyncio.Queue()
        self._drain_lock = asyncio.Lock()


_current_task: ContextVar[Task | None] = ContextVar(
    "agent_task", default=None
)


async def _drain_queue(task: Task):
    """
    Ensure only ONE drain loop runs per Task at a time.
    """
    if task._drain_lock.locked():
        return

    async with task._drain_lock:
        while not task.action_queue.empty():
            action = await task.action_queue.get()
            try:
                await action
            finally:
                task.action_queue.task_done()


def _execute(coro):
    task = _current_task.get()
    if task is None:
        raise Exception("Not in task context")

    # do not await to avoid race condition
    task.action_queue.put_nowait(coro)
    asyncio.create_task(_drain_queue(task))


async def _status_stream(message: cl.Message, status: str):
    tokens = status.split()
    status_chunk = ""
    for token in tokens:
        status_chunk += token + " "
        await message.stream_token(status_chunk, is_sequence=True)
        await asyncio.sleep(0.1)


def update_status(status: str):
    """
    Update the status of the CURRENT running task.
    Automatically creates a thinking message on first call.
    """
    task = _current_task.get()

    if task is None:
        raise Exception("Not in task context")

    _execute(_status_stream(task.msg, status))


@cl.action_callback("cancel_task")  # Optional: allow user to cancel
async def on_cancel(action):
    await cl.Message(content="Task cancelled.").send()


async def task_started():
    """Start a new isolated task status"""
    _current_task.set(Task())


async def task_completed():
    task = _current_task.get()
    if task is None:
        raise Exception("Not in task context")

    _execute(task.msg.send())
    # Wait for action_queue to drain
    await task.action_queue.join()


@asynccontextmanager
async def agent_task():
    """
    Use this context manager around any agent/task run.
    All update_status() calls inside will affect only this task's message.
    """
    parent_task = _current_task.set(None)
    try:
        await task_started()
        yield
    except Exception as e:
        update_status("Error occurred")
        raise
    finally:
        await task_completed()
        _current_task.reset(parent_task)
