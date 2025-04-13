import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

from output_agent.app.models import TaskState, JSONRPCResponse, TaskSendParams, JSONRPCError, JSONRPCRequest, \
    A2ARequest, SendTaskRequest

app = FastAPI()

HOST = os.getenv("AGENT_HOST", "localhost")
PORT = int(os.getenv("AGENT_PORT", 5005))

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
async def handle_jsonrpc(request: Request):
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
        html_stub = f"<html><body><h1>HTML for: {params.message.parts[0].text}</h1></body></html>"

        return JSONResponse(
            JSONRPCResponse(
                id=json_rpc_request.id,
                result={
                    "id": params.id,
                    "sessionId": params.sessionId,
                    "status": {
                        "state": TaskState.COMPLETED
                    },
                    "artifacts": [{
                        "name": "html-output",
                        "parts": [{
                            "type": "text",
                            "text": html_stub
                        }]
                    }],
                    "metadata": {}
                }
            ).model_dump(exclude_none=True)
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)


"""
curl -X POST http://localhost:5005/ \
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