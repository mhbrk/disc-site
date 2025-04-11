from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import List

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# In-memory message store for mocking
dummy_chat_log: List[str] = []


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("base.html", {"request": request})


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
    try:
        i = 0
        while True:
            i += 1
            await websocket.send_text(f"<p><strong>Section {i}</strong>: This is dynamic HTML content.</p>")
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass


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

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
