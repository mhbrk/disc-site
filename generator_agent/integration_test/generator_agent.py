import asyncio
import os
import uuid
from uuid import uuid4

from common.client import A2AClient
from common.constants import BUILDER_AGENT_TOPIC
from common.mock_server import start_mock_server
from common.model import TaskSendParams, TextPart, Message, SendTaskRequest, SendTaskStreamingRequest
from common.utils import publish_to_topic


async def send_task_to_agent_direct(session_id: str):
    client = A2AClient("http://localhost:8001")

    # Build structured message
    message = Message(
        role="user",
        parts=[
            TextPart(
                text="Create a minimalistic Hello world site. "
                     "Don’t ask questions. just do it. "
                     "Use generated image of balloons for the background.")
        ]
    )

    # Wrap in TaskSendParams
    task_params = TaskSendParams(
        id=f"task-{uuid4().hex}",
        sessionId=session_id,
        message=message
    )

    # TODO: I don't think model_dump is needed here because it's a pydantic model and model dump occurs later inside the client
    response = await client.send_task_streaming(task_params)

    print(response.model_dump())


async def send_task_to_agent_indirect(session_id: str):
    message = Message(
        role="user",
        parts=[TextPart(text="Generate a simple Hello World site.")]
    )
    task_id = f"task-{uuid4().hex}"
    task_params = TaskSendParams(id=task_id, sessionId=session_id, message=message)
    request = SendTaskStreamingRequest(params=task_params, id=str(uuid.uuid4()))

    await publish_to_topic(BUILDER_AGENT_TOPIC, request.model_dump(exclude_none=True), task_id)


async def tasks_completed():
    current = asyncio.current_task()
    tasks = [t for t in asyncio.all_tasks() if t is not current]

    if tasks:
        print(f"Waiting for {len(tasks)} tasks...")
        await asyncio.gather(*tasks)


async def test_invalid_request_type():
    message = Message(
        role="user",
        parts=[TextPart(text="Generate a simple Hello World site.")]
    )
    task_params = TaskSendParams(id="test-task", sessionId="user-1-session-1", message=message)
    request = SendTaskRequest(params=task_params, id=str(uuid.uuid4()))

    await publish_to_topic(BUILDER_AGENT_TOPIC, request.model_dump(exclude_none=True), "test-task")


async def test_success():
    session_id = os.getenv("SESSION_ID", "test-session")

    await send_task_to_agent_indirect(session_id)


# TODO: make this a pytest suite
async def test_success_direct():
    session_id = os.getenv("SESSION_ID", "test-session")

    await send_task_to_agent_direct(session_id)


async def main():
    # await start_mock_server()
    await test_success_direct()
    # await test_success()
    # await test_invalid_request_type()

    await tasks_completed()


if __name__ == "__main__":
    asyncio.run(main())
