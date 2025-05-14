import asyncio
import json
import logging
import os
import uuid
from typing import Any

import httpx
from google.cloud import pubsub_v1

import common
from common.constants import CHAT_AGENT_TOPIC
from common.model import TextPart, TaskSendParams, SendTaskRequest

PUBSUB_URL = os.getenv("PUBSUB_URL", "http://localhost:8000")
SUBSCRIBE_URL: str = f"{PUBSUB_URL}/subscribe"

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)


publisher = pubsub_v1.PublisherClient()
project_id = "breba-458921"


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

    await publish_to_topic(CHAT_AGENT_TOPIC, request.model_dump(exclude_none=True), task_id)


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
        logger.info(f"Subscribed to: {SUBSCRIBE_URL}, payload: {json.dumps(payload)}")


async def publish_to_topic(topic: str, payload: dict[str, Any], task_id: str):
    """
    Helper for publishing to Google Pub/Sub topic.
    """
    if os.environ.get("PUBSUB_URL") is None:
        logger.info("PUBSUB_URL not set. Using google pubsub.")
        await publish_to_google_topic(topic, payload, task_id)
    else:
        logger.info("PUBSUB_URL set. Using local pubsub.")
        await publish_to_local_topic(topic, payload, task_id)


async def publish_to_local_topic(topic: str, payload: dict[str, Any], task_id: str):
    """
    Helper for publishing to pubsub topic.
    :param topic: topic to  publish to
    :param payload: teh payload to publish to the topic
    :param task_id: for logging
    """
    # TODO: should be in a pubsub SDK (or use google pub sub locally)
    payload = {"topic": topic, "payload": payload}

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"[{task_id}] Publishing to pubsub: {payload}")
            await client.post(f"{PUBSUB_URL}/publish", json=payload)
        except Exception as e:
            logger.error(f"[{task_id}] Failed to publish to pubsub: {e}")


async def publish_to_google_topic(topic: str, payload: dict[str, Any], task_id: str):
    """
    Helper for publishing to Google Pub/Sub topic.
    """
    topic_path = publisher.topic_path(project_id, topic)

    # Serialize and encode the payload
    payload_bytes = json.dumps(payload).encode("utf-8")

    try:
        logger.info(f"[{task_id}] Publishing to pubsub topic {topic}: {payload}")
        future = publisher.publish(topic_path, payload_bytes)
        future.result()  # Block until the message is actually published
        logger.info(f"[{task_id}] Published to pubsub topic {topic}: {payload}")
    except Exception as e:
        logger.error(f"[{task_id}] Failed to publish to pubsub: {e}")


if __name__ == "__main__":
    async def run():
        await publish_to_google_topic("builder_agent_topic", {"test": "test"}, "test")


    asyncio.run(run())
