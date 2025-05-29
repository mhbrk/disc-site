import uuid

import chainlit as cl
from chainlit import Message

from orchestrator import process_user_message

task_id: str | None = None


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
    await process_user_message("user-1-session-1", message.content)
