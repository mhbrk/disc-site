import asyncio
import os
import uuid
from uuid import uuid4

import httpx
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import Config, Server

from common.constants import BUILDER_AGENT_TOPIC, GENERATOR_AGENT_TOPIC
from common.model import TaskSendParams, TextPart, Message, SendTaskRequest, SendTaskStreamingRequest
from common.utils import publish_to_topic, subscribe_to_agent

PUBSUB_URL = "http://127.0.0.1:8000"
RECEIVE_URL: str = "http://my-localhost:7999"
HOST = "127.0.0.1"
PORT = 7999

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.post("/agent/generator/push")
async def push_from_generator_agent(payload: dict = Body(...)):
    print(f"✅ Received payload from generator agent:\n{payload}")


async def wait_for_server_ready(url: str, timeout: float = 10.0):
    async with httpx.AsyncClient() as client:
        for _ in range(int(timeout * 10)):
            try:
                response = await client.get(url)
                if response.status_code < 500:
                    print("✅ Server is ready.")
                    return
            except httpx.RequestError:
                pass
            await asyncio.sleep(0.1)
    raise TimeoutError(f"Server did not start within {timeout} seconds")


async def send_task_to_agent_indirect(session_id: str):
    message = Message(
        role="user",
        parts=[TextPart(text="Generate a simple Hello World site.")]
    )
    task_id = f"task-{uuid4().hex}"
    task_params = TaskSendParams(id=task_id, sessionId=session_id, message=message)
    request = SendTaskStreamingRequest(params=task_params, id=str(uuid.uuid4()))

    await publish_to_topic(BUILDER_AGENT_TOPIC, request.model_dump(exclude_none=True), task_id)


async def run_uvicorn_in_background():
    config = Config(app=app, host=HOST, port=PORT, log_level="info", reload=False)
    server = Server(config=config)
    await server.serve()


async def tasks_completed():
    current = asyncio.current_task()
    tasks = [t for t in asyncio.all_tasks() if t is not current]

    if tasks:
        print(f"Waiting for {len(tasks)} tasks...")
        await asyncio.gather(*tasks)


async def start_listener():
    asyncio.create_task(run_uvicorn_in_background())
    asyncio.create_task(subscribe_to_agent(GENERATOR_AGENT_TOPIC, f"{RECEIVE_URL}/agent/generator/push"))


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


async def main():
    await start_listener()
    await wait_for_server_ready(f"http://{HOST}:{PORT}/docs")
    # await test_success()
    await test_invalid_request_type()

    await tasks_completed()


if __name__ == "__main__":
    asyncio.run(main())
