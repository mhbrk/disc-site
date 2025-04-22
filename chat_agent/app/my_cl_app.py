import os
import uuid

import chainlit as cl
import httpx
from chainlit import Message

import common
from common.model import TextPart, TaskSendParams, SendTaskRequest

PUBSUB_URL = os.getenv("PUBSUB_URL", "http://localhost:8000")
CHAT_AGENT_TOPIC: str = "chat_agent_topic"


async def send_task_to_builder_indirect(session_id: str, task_id: str, response: str):
    """
    Publish to chat agent topic.
    Builder should be listening and picking up tasks from this topic
    """
    message = common.model.Message(
        role="user",
        parts=[TextPart(text=response)])

    # Wrap in TaskSendParams
    task_params = TaskSendParams(
        id=task_id,
        sessionId=session_id,
        message=message
    )

    request = SendTaskRequest(
        params=task_params,
        id=str(uuid.uuid4())  # or pass your own
    )

    payload = {
        "topic": CHAT_AGENT_TOPIC,
        "payload": request.model_dump(exclude_none=True)
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"[{task_id}] Publishing to pubsub: {payload}")
            await client.post(f"{PUBSUB_URL}/publish", json=payload)
        except Exception as e:
            print(f"[{task_id}] Failed to publish to pubsub: {e}")


task_id: str | None = None


@cl.on_chat_start
async def main():
    global task_id
    task_id = f"task-{uuid.uuid4().hex}"
    await cl.Message(content="Hello World").send()


@cl.on_window_message
async def window_message(message: str):
    await cl.Message(content=message).send()


@cl.on_message
async def respond(message: Message):
    await send_task_to_builder_indirect("user-1-session-1", task_id, message.content)
