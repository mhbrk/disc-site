import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, Body
from fastapi.responses import JSONResponse

from models import TaskState, JSONRPCResponse, JSONRPCError, A2ARequest, SendTaskRequest
from task_manager import start_streaming_task

load_dotenv()

app = FastAPI()

HOST = os.getenv("AGENT_HOST", "localhost")
PORT = int(os.getenv("AGENT_PORT", 8001))


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
        params = json_rpc_request.params
        query = params.message.parts[0].text
        session_id = params.sessionId
        task_id = params.id

        # Start the streaming agent in the background
        background_tasks.add_task(start_streaming_task, task_id, session_id, query)

        html_stub = f"<html><body><h1>HTML for: {params.message.parts[0].text}</h1></body></html>"

        # Respond right away that the task was accepted
        return JSONResponse(
            JSONRPCResponse(
                id=json_rpc_request.id,
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
