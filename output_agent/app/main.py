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

from common.model import TaskState, JSONRPCResponse, JSONRPCError, A2ARequest, SendTaskRequest
from task_manager import start_streaming_task

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)


load_dotenv()


HOST = os.getenv("AGENT_HOST", "localhost")
PORT = int(os.getenv("AGENT_PORT", 8001))
PUBSUB_URL = os.getenv("PUBSUB_URL", "http://localhost:8000")

RECEIVE_URL: str = f"http://{HOST}:{PORT}"
BUILDER_AGENT_TOPIC: str = "builder_agent_topic"


async def subscribe_to_agents():
    # Receives tasks at root url
    # TODO: check for pubsub being up instead of sleeping
    await asyncio.sleep(2)
    payload = {"topic": BUILDER_AGENT_TOPIC, "endpoint": f"{RECEIVE_URL}/"}
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
    return JSONResponse({
        "name": "Output Agent",
        "description": "Generates an HTML web page given detailed specifications",
        "url": f"http://{HOST}:{PORT}",
        "version": "0.1.0",
        "capabilities": {
            "streaming": True,
            "pushNotifications": True,
            "stateTransitionHistory": False
        },
        "authentication": {
            "schemes": []
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "build-html",
                "name": "Build HTML pages with images",
                "description": "Builds complete HTML pages with optional images and styling.",
                "tags": ["html", "web", "design"],
                "examples": [
                    "Create an HTML landing page for a bakery with a hero image and about section",
                    "Generate an HTML page showcasing a product with pricing and contact form"
                ]
            }
        ]
    })


def execute_task(task_request: SendTaskRequest, background_tasks: BackgroundTasks):
    params = task_request.params
    query = params.message.parts[0].text
    session_id = params.sessionId
    task_id = params.id

    # Start the streaming agent in the background
    background_tasks.add_task(start_streaming_task, task_id, session_id, query)

    # TODO: publish this to topic so that listener can know that the task was registered a new response is coming
    # TODO: use SendTaskResponse type
    return JSONResponse(
        JSONRPCResponse(
            id=task_request.id,
            result={
                "id": task_id,
                "sessionId": session_id,
                "status": {
                    "state": TaskState.SUBMITTED,
                    "message": {
                        "role": "agent",
                        "parts": [{
                            "type": "text",
                            "text": "Streaming has started. You will receive updates shortly."
                        }]
                    }
                },
                "metadata": {}
            }
        ).model_dump(exclude_none=True)
    )


@app.post("/")
async def handle_jsonrpc(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()

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
        return execute_task(json_rpc_request, background_tasks)


@app.post("/echo")
def echo(payload: dict = Body(..., embed=False)):
    print(payload)
    return payload


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)

"""
curl -X POST http://localhost:8001/ \
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
