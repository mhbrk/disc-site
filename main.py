import asyncio
from typing import List, Annotated
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form, Body, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from common.model import SendTaskResponse

HOST = "localhost"
PORT = 7999
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key="my-super-secret-key")

templates = Jinja2Templates(directory="templates")

# In-memory message store for mocking
dummy_chat_log: List[str] = []

SUBSCRIBE_URL: str = "http://127.0.0.1:8000/subscribe"
PUSH_URL: str = "http://my-localhost:7999"
OUTPUT_AGENT_TOPIC: str = "output_agent_topic"

# Keeps track of the currently connected output sockets by sessionId
connected_output_sockets: dict[str, WebSocket] = {}

async def subscribe_to_agents():
    payload = {"topic": OUTPUT_AGENT_TOPIC, "endpoint": f"{PUSH_URL}/agent/output/push"}
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.post(SUBSCRIBE_URL, json=payload, headers=headers)
        response.raise_for_status()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # TODO: nees to be done at login
    request.session["sessionId"] = f"user-1-session-1"
    print(request.session.get("sessionId"))
    await subscribe_to_agents()
    return templates.TemplateResponse("base.html", {"request": request, "socket_server": f"ws://{HOST}:{PORT}"})


@app.post("/message", response_class=HTMLResponse)
async def post_message(request: Request, message: str = Form(...)):
    dummy_chat_log.append(f"<div class='text-end text-primary'>You: {message}</div>")
    dummy_chat_log.append(f"<div class='text-start text-success'>Bot: Responding to '{message}'...</div>")
    return templates.TemplateResponse("partials/chat_messages.html", {
        "request": request,
        "messages": dummy_chat_log[-2:]  # Only return new messages
    })


@app.websocket("/ws/input")
async def ws_input(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_text(
                '<div id="chat-messages" hx-swap-oob="beforeend">'
                "<div class='text-muted'>System: Input stream alive...</div>"
                "</div>"
            )
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/processing")
async def ws_processing(websocket: WebSocket):
    await websocket.accept()
    try:
        i = 0
        while True:
            i += 1
            # Simulate new log content (mocked)
            log_content = f"Step {i}...\nStep {i + 1}...\nStep {i + 2}..."
            await websocket.send_text(log_content)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/output")
async def ws_output(websocket: WebSocket):
    await websocket.accept()
    session_id = websocket.session.get("sessionId", "anonymous")
    connected_output_sockets[session_id] = websocket
    try:
        i = 0
        while True:
            i += 1
            # TODO: Need to just check how to keep alive
            await asyncio.sleep(20)
    except WebSocketDisconnect:
        connected_output_sockets.pop(session_id, None)
        print(f"Disconnected session: {session_id}")


@app.post("/agent/output/push")
async def push_from_output_agent(payload: dict = Body(...)):
    print(f"Received payload from output agent: {payload}")
    task_response = SendTaskResponse.model_validate(payload)
    session_id = task_response.result.sessionId
    print(f"Received task session_id: {session_id}")
    websocket = connected_output_sockets.get(session_id)
    if websocket:
        text = task_response.result.artifacts[0].parts[0].text
        print(f"[{session_id}] Sending text: {text}")
        await websocket.send_text(task_response.result.artifacts[0].parts[0].text)
    return {"status": "success"}


@app.post("/echo")
async def echo(payload: dict = Body(...)):
    print(payload)
    return payload


@app.get("/preview", response_class=HTMLResponse)
async def preview():
    html = """
    <!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: sans-serif; padding: 1rem; }
        #output-container { border: 1px dashed #ccc; padding: 1rem; }
    </style>
</head>
<body>
    <h3>Live HTML Preview</h3>
    <div id="output-container"></div>

    <script>
    window.addEventListener("message", (event) => {
        if (event.data.type === "append-html") {
            const container = document.getElementById("output-container");
            const fragment = document.createRange().createContextualFragment(event.data.html);
            container.appendChild(fragment);
        }
    });
    </script>
</body>
</html>
    """
    return html


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
