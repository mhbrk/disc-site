import asyncio

import httpx
from fastapi import FastAPI, Body
from starlette.middleware.cors import CORSMiddleware
from uvicorn import Config, Server

from common.constants import GENERATOR_AGENT_TOPIC
from common.utils import subscribe_to_agent

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


async def run_uvicorn_in_background():
    config = Config(app=app, host=HOST, port=PORT, log_level="info", reload=False)
    server = Server(config=config)
    await server.serve()


async def start_mock_server():
    asyncio.create_task(run_uvicorn_in_background())
    asyncio.create_task(subscribe_to_agent(GENERATOR_AGENT_TOPIC, f"{RECEIVE_URL}/agent/generator/push"))
    await wait_for_server_ready(f"http://{HOST}:{PORT}/docs")
