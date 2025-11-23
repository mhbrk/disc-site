import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Optional

import chainlit as cl

THINKING = "Thinking..."
DONE = "Done"

# This will hold the current status message for the current task/context
_current_status_msg: ContextVar[Optional[cl.Message]] = ContextVar(
    "agent_status_message", default=None
)


def update_status(status: str):
    """
    Update the status of the CURRENT running task.
    Automatically creates a thinking message on first call.
    """
    msg = _current_status_msg.get()

    if msg is None:
        raise Exception("Not in task context")

    msg.content = status
    asyncio.create_task(msg.update())


async def remove_status():
    """Force remove current status message"""
    msg = _current_status_msg.get()
    if msg:
        await msg.remove()
        _current_status_msg.set(None)


@cl.action_callback("cancel_task")  # Optional: allow user to cancel
async def on_cancel(action):
    await remove_status()
    await cl.Message(content="Task cancelled.").send()


async def task_started():
    """Start a new isolated task status"""
    msg = cl.Message(content=THINKING)
    await msg.send()
    _current_status_msg.set(msg)


async def task_completed():
    _current_status_msg.set(None)


@asynccontextmanager
async def agent_task():
    """
    Use this context manager around any agent/task run.
    All update_status() calls inside will affect only this task's message.
    """
    token = _current_status_msg.set(None)  # Reset for this task
    try:
        await task_started()  # Auto-show thinking
        yield
    except Exception as e:
        update_status("Error occurred")
        raise
    finally:
        await task_completed()
        _current_status_msg.reset(token)  # Clean up