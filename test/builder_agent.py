import asyncio
import uuid
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, Body
from uvicorn import Server, Config

from common.client import A2AClient
from common.model import TaskSendParams, TextPart, Message, SendTaskRequest, SendTaskResponse, TaskState
from common.utils import subscribe_to_agent

PUBSUB_URL: str = "http://127.0.0.1:8000"
ASK_CHAT_AGENT_URL: str = "http://my-localhost:7998/echo"
BUILDER_AGENT_TOPIC: str = "builder_agent_topic"
ASK_CHAT_AGENT_TOPIC: str = "ask_chat_agent_topic"
CHAT_AGENT_TOPIC: str = "chat_agent_topic"


async def send_task_to_agent_direct(session_id: str):
    client = A2AClient("http://localhost:8002")

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


async def send_task_to_builder_indirect(session_id: str, task_id: str, response: str):
    """
    Publish to chat agent topic.
    Builder should be listening and picking up tasks from this topic
    """
    message = Message(
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


builder_response: SendTaskResponse | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await subscribe_to_agent(ASK_CHAT_AGENT_TOPIC, ASK_CHAT_AGENT_URL)
    yield
    # TODO: unsubscribe


app = FastAPI(lifespan=lifespan)


@app.post("/echo")
async def echo(payload: dict = Body(..., embed=False)):
    global builder_response
    print(f"Echo received payload: {payload}")
    builder_response = payload
    return payload


async def start_uvicorn():
    config = Config(app=app, host="localhost", port=7998, reload=False, loop="asyncio")
    server = Server(config)
    await server.serve()


async def run_test():
    global builder_response
    await send_task_to_builder_indirect(
        "user-1-session-1",
        f"task-{uuid4().hex}",
        "Generate a site for my birthday. I'm turning 18. My birthday is on June 11 and the theme is 1990s."
    )

    while True:
        await asyncio.sleep(1)
        if builder_response:
            print(builder_response)
            task_response = SendTaskResponse.model_validate(builder_response)
            task = task_response.result
            if task.status.state == TaskState.INPUT_REQUIRED:
                builder_response = None
                await send_task_to_builder_indirect(task.sessionId, task.id, "Just do what you think is best")
            else:
                print(task.artifacts[0].parts[0].text)
                break


async def main():
    # Run the server in the background
    server_task = asyncio.create_task(start_uvicorn())
    await asyncio.sleep(2)

    # Run your test
    await run_test()

    # Optionally: cancel server after test
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
