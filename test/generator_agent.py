import asyncio
import os
import uuid
from uuid import uuid4

import httpx

from common.client import A2AClient
from common.model import TaskSendParams, TextPart, Message, SendTaskRequest

PUBSUB_URL: str = "http://127.0.0.1:8000"
GENERATOR_AGENT_TOPIC: str = "generator_agent_topic"


async def send_task_to_agent_direct(session_id: str):
    client = A2AClient("http://localhost:8001")

    # Build structured message
    message = Message(
        role="user",
        parts=[
            TextPart(
                text="Generate a site for my birthday. I'm turning 18. My birthday is on June 11 and the theme is 1990s.")
        ]
    )

    # Wrap in TaskSendParams
    task_params = TaskSendParams(
        id=f"task-{uuid4().hex}",
        sessionId=session_id,
        message=message
    )

    # Send the task
    # TODO: I don't think model_dump is needed here because it's a pydantic model and model dump occurs later inside the client
    response = await client.send_task(task_params)

    # Print the structured response
    print(response.model_dump())


async def send_task_to_agent_indirect(session_id: str):
    message = Message(
        role="user",
        parts=[
            TextPart(
                text="Generate a site for my birthday. I'm turning 18. My birthday is on June 11 and the theme is 1990s.")
        ]
    )

    # Wrap in TaskSendParams
    task_id = f"task-{uuid4().hex}"
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
        "topic": "builder_agent_topic",
        "payload": request.model_dump(exclude_none=True)
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"[{task_id}] Publishing to pubsub: {payload}")
            await client.post(f"{PUBSUB_URL}/publish", json=payload)
        except Exception as e:
            print(f"[{task_id}] Failed to publish to pubsub: {e}")


asyncio.run(send_task_to_agent_indirect(os.environ.get("SESSION_ID")))
