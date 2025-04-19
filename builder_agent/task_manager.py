import os
import uuid

import httpx
from dotenv import load_dotenv

from common.model import TextPart, Message, Artifact, TaskStatus, TaskState, Task, SendTaskResponse, SendTaskRequest, \
    TaskSendParams

load_dotenv()

from agent import agent

PUBSUB_URL = os.environ.get("PUBSUB_URL", "http://localhost:8000")
PUBSUB_BUILDER_TOPIC = "builder_agent_topic"


class AgentTaskManager:

    async def on_send_task(self, request: SendTaskRequest):
        agent_response = await agent.invoke(request.params.sessionId, request.params.message)
        content = agent_response.get("content")
        is_task_completed = agent_response.get("is_task_complete")

        if is_task_completed:
            task_status = TaskStatus(state=TaskState.COMPLETED)
        else:
            # When we are invoking the agent, if task is not complete, we assume it is waiting for user input
            # Even if there is an error, the only resolution that is possible, is another message from client
            message = Message(role="agent", parts=[TextPart(text=content)])
            task_status = TaskStatus(message=message, state=TaskState.INPUT_REQUIRED)
            # Clear content, because we don't have an artifact, instead we are looking for an answer
            content = ""

        artifact = Artifact(parts=[TextPart(text=content)])

        task_id = request.params.id
        task = Task(
            id=task_id,
            sessionId=request.params.sessionId,
            status=task_status,
            artifacts=[artifact],  # or keep None if artifacts are sent at the end
            metadata={}
        )

        response = SendTaskResponse(id=task_id, result=task)

        payload = {
            "topic": PUBSUB_BUILDER_TOPIC,
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

    task_manager = AgentTaskManager()
    message = Message(
        role="user",
        parts=[
            TextPart(
                text="Generate a site for my birthday. I'm turning 18. My birthday is on June 11 and the theme is 1990s.")
        ]
    )

    # Wrap in TaskSendParams
    task_id = f"task-{uuid.uuid4().hex}"
    task_params = TaskSendParams(
        id=task_id,
        sessionId="user-1-session-1",
        message=message
    )

    test_request = SendTaskRequest(
        params=task_params,
        id=str(uuid.uuid4())  # or pass your own
    )
    asyncio.run(task_manager.on_send_task(test_request))
