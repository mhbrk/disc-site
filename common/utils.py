import os
import uuid

import httpx

import common
from common.model import TextPart, TaskSendParams, SendTaskRequest

PUBSUB_URL = os.getenv("PUBSUB_URL", "http://localhost:8000")
SUBSCRIBE_URL: str = f"{PUBSUB_URL}/subscribe"

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



async def subscribe_to_agent(topic, endpoint):
    """
    Helper function to subscribe to a pubsub topic. Should ideally be inside pubsub SDK.
    :param topic: topic name to listen to
    :param endpoint: endpoint to which pubsub will push data to
    :return: coroutine
    """
    payload = {"topic": topic, "endpoint": endpoint}
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.post(SUBSCRIBE_URL, json=payload, headers=headers)
        response.raise_for_status()