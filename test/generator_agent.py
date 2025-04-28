import asyncio
import os
import uuid
from uuid import uuid4

from common.client import A2AClient
from common.constants import BUILDER_AGENT_TOPIC
from common.model import TaskSendParams, TextPart, Message, SendTaskRequest
from common.utils import publish_to_topic

PUBSUB_URL: str = "http://127.0.0.1:8000"


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

    await publish_to_topic(BUILDER_AGENT_TOPIC, request.model_dump(exclude_none=True), task_id)


asyncio.run(send_task_to_agent_indirect(os.environ.get("SESSION_ID")))
