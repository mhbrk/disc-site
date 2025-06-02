import uuid

import chainlit as cl
from chainlit import Message

from orchestrator import process_chat_message

task_id: str | None = None

async def builder_completed(payload: str):
    await cl.send_window_message(payload)

@cl.on_chat_start
async def main():
    global task_id
    task_id = f"task-{uuid.uuid4().hex}"
    await cl.Message(
        content="Hello, I'm here to assist you with building your website. We can build it together one step at a time,"
                " or you can give me the full specification, and I will have it built.").send()


@cl.on_window_message
async def window_message(message: str):
    await cl.Message(content=message).send()


@cl.on_message
async def respond(message: Message):
    # session_id = cl.user_session.get("id")
    session_id = "user-1-session-1"  # hardcoded for now
    await process_chat_message(session_id, message.content, builder_completed)
