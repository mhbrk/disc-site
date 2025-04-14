from datetime import datetime
import os

import httpx

from dotenv import load_dotenv

from models import TextPart, Message, Artifact, TaskStatus, TaskState, Task, SendTaskResponse

load_dotenv()

from agent import agent

PUBSUB_URL = os.environ.get("PUBSUB_URL", "http://localhost:8000")
PUBSUB_TOPIC = "output_agent_topic"


async def start_streaming_task(task_id: str, session_id: str, query: str):
    async for chunk in agent.stream(query, session_id):
        content = chunk.get("content")
        if not content:
            continue

        is_task_completed = chunk.get("is_task_complete")

        if is_task_completed:
            task_status = TaskStatus(state=TaskState.COMPLETED)
        else:
            message = Message(role="agent", parts=[TextPart(text="Streaming...")])
            task_status = TaskStatus(message=message, state=TaskState.WORKING)

        artifact = Artifact(parts=[TextPart(text=content)])

        task = Task(
            id=task_id,
            sessionId=session_id,
            status=task_status,
            artifacts=[artifact],  # or keep None if artifacts are sent at the end
            metadata={}
        )

        response = SendTaskResponse(id=task_id, result=task)

        payload = {
            "topic": PUBSUB_TOPIC,
            "payload": response.model_dump(exclude_none=True)
        }

        async with httpx.AsyncClient() as client:
            try:
                print(f"[{task_id}] Publishing to pubsub: {payload}")
                await client.post(f"{PUBSUB_URL}/publish", json=payload)
            except Exception as e:
                print(f"[{task_id}] Failed to publish to pubsub: {e}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(start_streaming_task("abc123", "def456", "generate a hello world site"))
