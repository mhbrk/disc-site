import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, Body
from fastapi.responses import JSONResponse

from common.constants import BUILDER_AGENT_TOPIC
from common.model import JSONRPCResponse, JSONRPCError, A2ARequest, SendTaskStreamingRequest
from common.utils import subscribe_to_agent
from task_manager import execute_task

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

load_dotenv()

HOST = os.getenv("AGENT_HOST", "localhost")
PORT = int(os.getenv("AGENT_PORT", 8001))

RECEIVE_URL: str = f"http://{HOST}:{PORT}"


async def subscribe_to_agents():
    # TODO: check for pubsub being up instead of sleeping
    await asyncio.sleep(2)
    await subscribe_to_agent(BUILDER_AGENT_TOPIC, RECEIVE_URL)


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

    if isinstance(json_rpc_request, SendTaskStreamingRequest):
        return JSONResponse(await execute_task(json_rpc_request))


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
          "text": "generate a hello world site"
        }]
      }
    }
  }'
"""
