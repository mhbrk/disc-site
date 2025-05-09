import logging
import os

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

RECEIVE_URL = os.getenv("RECEIVE_URL", "http://0.0.0.0:8080")

task_manager = AgentTaskManager()

app = FastAPI()


@app.get("/.well-known/agent.json")
async def get_agent_card():
    """
    Returns the agent card for discoverability. Not used yet
    """
    capabilities = AgentCapabilities(streaming=True)
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
        url=RECEIVE_URL,
        version="1.0.0",
        defaultInputModes=BuilderAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=BuilderAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill],
    )
    return JSONResponse(card.model_dump(exclude_none=True))


@app.post("/")
async def handle_jsonrpc(request: Request, background_tasks: BackgroundTasks):
    """
    Handles Incoming requests. Currently, supports only SendTaskRequest
    :param request: The request to process
    :param background_tasks: used for async tasks (not used yet)
    """
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
    else:
        response: JSONRPCResponse = JSONRPCResponse(
            response_method="tasks/send",
            id=body.get("id"),
            error=JSONRPCError(code=-32600, message="Invalid JSON-RPC request")
        )
        await task_manager.handle_error(response.model_dump(exclude_none=True), body.get("params", {}).get("id"))
        return JSONResponse(response.model_dump(exclude_none=True), status_code=400)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/echo")
def echo(payload: dict = Body(..., embed=False)):
    print(payload)
    return payload


if __name__ == "__main__":
    host = os.getenv("AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host=host, port=port, reload=True)

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
