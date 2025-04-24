import asyncio
import logging
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from common.model import SendTaskResponse, TaskState, SendTaskRequest, FilePart, TextPart
from common.utils import send_task_to_builder_indirect

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

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

app.mount("/images", StaticFiles(directory="./images"), name="images")

templates = Jinja2Templates(directory="templates")

PUBSUB_URL: str = "http://127.0.0.1:8000"
SUBSCRIBE_URL: str = f"{PUBSUB_URL}/subscribe"
PUSH_URL: str = "http://my-localhost:7999"
GENERATOR_AGENT_TOPIC: str = "generator_agent_topic"
ASK_CHAT_AGENT_TOPIC: str = "ask_chat_agent_topic"
CHAT_AGENT_TOPIC: str = "chat_agent_topic"
BUILDER_AGENT_TOPIC: str = "builder_agent_topic"

# Keeps track of the currently connected generator sockets by sessionId
connected_generator_sockets: dict[str, WebSocket] = {}
connected_input_sockets: dict[str, WebSocket] = {}
connected_processing_sockets: dict[str, WebSocket] = {}


async def subscribe_to_agents():
    payload = {"topic": GENERATOR_AGENT_TOPIC, "endpoint": f"{PUSH_URL}/agent/generator/push"}
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.post(SUBSCRIBE_URL, json=payload, headers=headers)
        response.raise_for_status()

    payload = {"topic": ASK_CHAT_AGENT_TOPIC, "endpoint": f"{PUSH_URL}/agent/chat/push"}
    async with httpx.AsyncClient() as client:
        response = await client.post(SUBSCRIBE_URL, json=payload, headers=headers)
        response.raise_for_status()

    payload = {"topic": BUILDER_AGENT_TOPIC, "endpoint": f"{PUSH_URL}/agent/builder/push"}
    async with httpx.AsyncClient() as client:
        response = await client.post(SUBSCRIBE_URL, json=payload, headers=headers)
        response.raise_for_status()


async def handle_socket_connection(
        websocket: WebSocket,
        socket_registry: dict,
        session_key: str = "sessionId",
        ping_interval: float = 300.0,
):
    await websocket.accept()
    session_id = websocket.session.get(session_key, "anonymous")
    socket_registry[session_id] = websocket
    logger.info(f"Connected socket for session: {session_id}")

    try:
        while True:
            await asyncio.sleep(1)
            # await websocket.send_text("__ping__")
            # pong = await asyncio.wait_for(websocket.receive_text(), timeout=ping_interval)
            # if pong != "__pong__":
            #     raise WebSocketDisconnect(1006, f"Pong not received: {pong}")
    except asyncio.TimeoutError:
        logger.info(f"Disconnected socket for session: {session_id}, due to timeout")
    except WebSocketDisconnect:
        logger.info(f"Disconnected socket for session: {session_id}")
    finally:
        socket_registry.pop(session_id, None)
        await websocket.close()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # TODO: nees to be done at login
    request.session["sessionId"] = f"user-1-session-1"
    logger.info(f"Session ID: {request.session.get('sessionId')}")
    await subscribe_to_agents()
    return templates.TemplateResponse("base.html", {"request": request, "socket_server": f"ws://{HOST}:{PORT}"})


@app.websocket("/ws/input")
async def ws_input(websocket: WebSocket):
    await handle_socket_connection(websocket, connected_input_sockets)


@app.post("/agent/chat/push")
async def push_to_chat_agent(payload: dict = Body(...)):
    logger.info(f"Received payload for chat agent: {payload}")
    task_response = SendTaskResponse.model_validate(payload)
    session_id = task_response.result.sessionId
    logger.info(f"Chat agent received task for session_id: {session_id}")
    websocket = connected_input_sockets.get(session_id)
    if websocket:
        task = task_response.result
        if task.status.state == TaskState.INPUT_REQUIRED:
            await websocket.send_text(task.status.message.parts[0].text)
    else:
        logger.warning(f"No connected input socket found for session: {session_id}")
    return {"status": "success"}


@app.websocket("/ws/processing")
async def ws_processing(websocket: WebSocket):
    await handle_socket_connection(websocket, connected_processing_sockets)


@app.post("/agent/builder/run")
async def send_spec_to_builder(spec: dict = Body(...)):
    logger.info(f"Received spec from user: {spec}")
    task_id = f"task-{uuid.uuid4().hex}"
    prompt = f"This is the final prompt. Just process it. I will not answer any questiosn: {spec['body']}"
    await send_task_to_builder_indirect("user-1-session-1", task_id, prompt)
    return {"status": "success", "taskId": task_id}


@app.post("/agent/builder/push")
async def push_from_builder_agent(payload: dict = Body(...)):
    logger.info(f"Received payload from builder agent: {payload}")
    task_request = SendTaskRequest.model_validate(payload)
    session_id = task_request.params.sessionId
    logger.info(f"Received task session_id: {session_id}")
    websocket = connected_processing_sockets.get(session_id)
    if websocket:
        await websocket.send_text(task_request.params.message.parts[0].text)
    else:
        logger.warning(f"No connected generator socket found for session: {session_id}")
    return {"status": "success"}


@app.websocket("/ws/generator")
async def ws_generator(websocket: WebSocket):
    await handle_socket_connection(websocket, connected_generator_sockets)


@app.post("/agent/generator/push")
async def push_from_generator_agent(payload: dict = Body(...)):
    logger.info(f"Received payload from generator agent: {payload}")
    task_response = SendTaskResponse.model_validate(payload)
    session_id = task_response.result.sessionId
    logger.info(f"Received task session_id: {session_id}")
    websocket = connected_generator_sockets.get(session_id)
    if websocket:
        main_part = task_response.result.artifacts[0].parts[0]
        if isinstance(main_part, FilePart):
            # If we received a file, we want to save it and reload the page
            response = await httpx.AsyncClient().get(main_part.file.uri)
            image = response.content
            images_dir = Path("images")
            images_dir.mkdir(parents=True, exist_ok=True)
            image_path = images_dir / main_part.file.name
            image_path.write_bytes(image)
            await websocket.send_text("__reload__")
        elif isinstance(main_part, TextPart):
            if task_response.result.status.state == TaskState.WORKING:
                text = main_part.text
                logger.info(f"[{session_id}] Sending text: {text}")
                await websocket.send_text(task_response.result.artifacts[0].parts[0].text)
            if task_response.result.status.state == TaskState.COMPLETED:
                await websocket.send_text("__completed__")
        else:
            logger.error(f"Unhandled part type: {type(main_part)} - {main_part}")
    else:
        logger.warning(f"No connected generator socket found for session: {session_id}")
    return {"status": "success"}


@app.post("/echo")
async def echo(payload: dict = Body(...)):
    logger.info(payload)
    return payload


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
