import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, Body
from fastapi.responses import JSONResponse

from builder_agent.agent import BuilderAgent
from common.model import JSONRPCResponse, JSONRPCError, A2ARequest, SendTaskRequest, AgentCard, AgentSkill, \
    AgentCapabilities
from task_manager import AgentTaskManager

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

load_dotenv()

HOST = os.getenv("AGENT_HOST", "localhost")
PORT = int(os.getenv("AGENT_PORT", 8002))
PUBSUB_URL = os.getenv("PUBSUB_URL", "http://localhost:8000")

RECEIVE_URL: str = f"http://{HOST}:{PORT}"
CHAT_AGENT_TOPIC: str = "chat_agent_topic"

task_manager = AgentTaskManager()


async def subscribe_to_agents():
    # Receives tasks at root url
    # TODO: check for pubsub being up instead of sleeping
    await asyncio.sleep(2)
    payload = {"topic": CHAT_AGENT_TOPIC, "endpoint": f"{RECEIVE_URL}/"}
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{PUBSUB_URL}/subscribe", json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Subscribed to: SUBSCRIBE_URL, payload: {json.dumps(payload)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await subscribe_to_agents()
    yield
    # TODO: unsubscribe


app = FastAPI(lifespan=lifespan)


@app.get("/.well-known/agent.json")
async def get_agent_card():
    capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
    skill = AgentSkill(
        id="builder_prompt",
        name="Builder Prompt for Website Generator",
        description="Generates detailed specification for the website generator agent to consume",
        tags=["prompt generator", "website specifications"],
        examples=[
            "Build a website for my birthday party. I'm turning 18. My birthday is on June 11 and the theme is 1990s?"],
    )

    card = AgentCard(
        name="Currency Agent",
        description="Helps with exchange rates for currencies",
        url=f"http://{HOST}:{PORT}/",
        version="1.0.0",
        defaultInputModes=BuilderAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=BuilderAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill],
    )
    return JSONResponse(card.model_dump(exclude_none=True))


@app.post("/")
async def handle_jsonrpc(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()

    logger.info(f"Received request: {body}")

    try:
        json_rpc_request = A2ARequest.validate_python(body)
    except Exception as e:
        return JSONResponse(
            JSONRPCResponse(
                id=body.get("id"),
                error=JSONRPCError(code=-32600, message="Invalid JSON-RPC request", data=str(e))
            ).model_dump(exclude_none=True),
            status_code=400
        )

    if isinstance(json_rpc_request, SendTaskRequest):
        return await task_manager.on_send_task(json_rpc_request)


@app.post("/echo")
def echo(payload: dict = Body(..., embed=False)):
    print(payload)
    return payload


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)

"""
curl -X POST http://localhost:8002/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tasks/send",
    "params": {
      "id": "abc123",
      "message": {
        "role": "user",
        "parts": [{
          "type": "text",
          "text": "generate an html resume"
        }]
      }
    }
  }'
"""
