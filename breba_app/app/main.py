import asyncio
import logging
import os
import uuid
from pathlib import Path

import httpx
from chainlit.utils import mount_chainlit
from fastapi import FastAPI, Request, WebSocket, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from act_agent.agent import invoke_act_agent
from common.constants import CHAT_AGENT_TOPIC, ASK_CHAT_AGENT_TOPIC, BUILDER_AGENT_TOPIC, GENERATOR_AGENT_TOPIC
from common.google_pub_sub import extract_pubsub_message
from common.model import SendTaskResponse, TaskState, SendTaskRequest, FilePart, TextPart, A2AResponse, \
    SendTaskStreamingResponse, TaskStatusUpdateEvent, JSONRPCMessage, TaskArtifactUpdateEvent, A2ARequest, Artifact
from common.utils import subscribe_to_agent
from orchestrator import process_user_message
from ui_bridge import UIBridge

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

SESSION_KEY = "sessionId"

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

# my-localhost is defined as parent host in pubsub container, should decouple this through config
RECEIVE_URL: str = os.getenv("RECEIVE_URL", "")

# Keeps track of the currently connected WebSockets by sessionId
user_ui_bridges: dict[str, UIBridge] = {}


async def subscribe_to_agents():
    """
    Subscribe to all the agents for the application
    """
    if not RECEIVE_URL:
        return

    await asyncio.gather(
        asyncio.create_task(subscribe_to_agent(CHAT_AGENT_TOPIC, f"{RECEIVE_URL}/agent/chat/push")),
        asyncio.create_task(subscribe_to_agent(ASK_CHAT_AGENT_TOPIC, f"{RECEIVE_URL}/agent/chat/ask")),
        asyncio.create_task(subscribe_to_agent(BUILDER_AGENT_TOPIC, f"{RECEIVE_URL}/agent/builder/push")),
        asyncio.create_task(subscribe_to_agent(GENERATOR_AGENT_TOPIC, f"{RECEIVE_URL}/agent/generator/push")),
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Home page route
    """
    # Hardcode to simulate a user logging in
    session_id = "user-1-session-1"
    request.session["sessionId"] = session_id
    user_ui_bridges[session_id] = UIBridge(session_id)

    logger.info(f"Session ID: {request.session.get('sessionId')}")
    await subscribe_to_agents()
    return templates.TemplateResponse("base.html", {"request": request, "chat_url": os.getenv("CHAT_URL")})


# TODO: source should be part of the model
async def update_status(session_id: str, source: str, model: JSONRPCMessage):
    """
    Updates status panel
    :param session_id: used to find the right WebSocket
    :param source: Who is sending the message
    :param model: JSONRPCMessage to report status on
    """
    # TODO: needs better pattern than if else
    socket = user_ui_bridges.get(session_id).status_socket
    status = None
    if socket:
        if isinstance(model, SendTaskRequest):
            status = {"source": source, "message": f"Requested task: {model.params.id}"}
        elif isinstance(model, SendTaskResponse):
            status = {"source": source, "message": f"[{model.result.id}] {model.result.status.state}"}
        elif isinstance(model, SendTaskStreamingResponse):
            # For streaming responses, we only care about TaskStatusUpdate, not artifact updates
            if isinstance(model.result, TaskStatusUpdateEvent):
                status = {"source": source, "message": f"[{model.result.id}] {model.result.status.state}"}

        if status:
            await socket.send_json(status)
    else:
        logger.error(f"No connected status socket found for session: {session_id}")


@app.websocket("/ws/status")
async def ws_status(websocket: WebSocket):
    """
    Establish WebSocket connection to the client.
    :param websocket: the client websocket
    """
    session_id = websocket.session.get(SESSION_KEY, "anonymous")
    bridge = user_ui_bridges[session_id]
    await bridge.add_status_socket(websocket)


@app.websocket("/ws/input")
async def ws_input(websocket: WebSocket):
    """
    Establish WebSocket connection to the client.
    :param websocket: the client websocket
    """
    session_id = websocket.session.get(SESSION_KEY, "anonymous")
    bridge = user_ui_bridges[session_id]
    await bridge.add_user_socket(websocket)


@app.post("/agent/chat/push")
async def message_from_chat_agent(payload: dict = Body(...)):
    """
    Handles push from chat agent. Usually to starting or confirming a user's task
    :param payload: Should be a SendTaskRequest
    """
    logger.info(f"Received payload from chat agent: {payload}")
    payload = extract_pubsub_message(payload)
    # TODO: handle validation errors
    task = SendTaskRequest.model_validate(payload)
    await update_status(task.params.sessionId, "chat", task)


@app.post("/agent/chat/ask")
async def push_to_chat_agent(payload: dict = Body(...)):
    """
    Handles push to chat agent. Usually to ask for input
    :param payload: Should be a SendTaskResponse
    """
    logger.info(f"Received payload for chat agent: {payload}")
    payload = extract_pubsub_message(payload)
    task_response = SendTaskResponse.model_validate(payload)
    session_id = task_response.result.sessionId
    logger.info(f"Chat agent received task for session_id: {session_id}")
    # TODO: again this we need to add source of the model
    await update_status(session_id, "to_chat", task_response)
    websocket = user_ui_bridges.get(session_id).user_socket
    if websocket:
        task = task_response.result
        if task.status.state == TaskState.INPUT_REQUIRED:
            await websocket.send_text(task.status.message.parts[0].text)
    else:
        logger.warning(f"No connected input socket found for session: {session_id}")
    return {"status": "success"}


@app.websocket("/ws/processing")
async def ws_processing(websocket: WebSocket):
    """
    Handles WebSocket connection for builder panel
    :param websocket: WebSocket from the client
    """
    session_id = websocket.session.get(SESSION_KEY, "anonymous")
    bridge = user_ui_bridges[session_id]
    await bridge.add_builder_socket(websocket)


@app.post("/agent/builder/run")
async def send_spec_to_builder(spec: dict = Body(...)):
    """
    Handles spec updates from the builder panel. This is the "Run" button. The spec will go through the builder agent,
    but with an additional instruction to run without modification.
    We want to run the spec by the builder to make sure that the builder agent is aware of our spec updates.
    :param spec: Requirements to run.
    """
    logger.info(f"Received spec from user: {spec}")
    task_id = f"task-{uuid.uuid4().hex}"
    prompt = f"This is the final prompt. Just process it. I will not answer any questions: {spec['body']}"
    await process_user_message("user-1-session-1", prompt)
    return {"status": "success", "taskId": task_id}


@app.post("/agent/builder/inline-comment")
async def send_spec_to_builder(data: dict = Body(...)):
    logger.info(f"Received spec from user: {data}")
    task_id = f"task-{uuid.uuid4().hex}"
    prompt = (f"Given the generated HTML page, the user selected the following text: {data["selection"]}. "
              f"The user comment regarding this text is:  {data["query"]}. Do not ask questions, just do it.")
    await process_user_message("user-1-session-1", prompt)
    return {"status": "success", "taskId": task_id}


@app.post("/agent/builder/push")
async def push_from_builder_agent(payload: dict = Body(...)):
    """
    Handles push from builder agent. This is the final spec that is expected to be picked up by the generator agent
    :param payload: The request to the generator agent (or whoever needs to know about builder spec)
    """
    logger.info(f"Received payload from builder agent: {payload}")
    payload = extract_pubsub_message(payload)
    task_request = A2ARequest.validate_python(payload)
    session_id = task_request.params.sessionId
    logger.info(f"Received task session_id: {session_id}")
    websocket = user_ui_bridges.get(session_id).builder_socket
    await update_status(session_id, "builder", task_request)
    if websocket:
        await websocket.send_text(task_request.params.message.parts[0].text)
    else:
        logger.warning(f"No connected generator socket found for session: {session_id}")
    return {"status": "success"}


@app.websocket("/ws/generator")
async def ws_generator(websocket: WebSocket):
    """
    Handles WebSocket connection for the generator panel
    :param websocket: WebSocket from the client
    """
    session_id = websocket.session.get(SESSION_KEY, "anonymous")
    bridge = user_ui_bridges[session_id]
    await bridge.add_generator_socket(websocket)


@app.post("/agent/generator/push")
async def push_from_generator_agent(payload: dict = Body(...)):
    """
    Handles push from the generator agent. This will be streaming html tags or a complete html page
    :param payload: Should be task response of some kind
    :return:
    """
    logger.info(f"Received payload from generator agent: {payload}")
    payload = extract_pubsub_message(payload)
    task_response = A2AResponse.validate_python(payload)

    if isinstance(task_response, SendTaskResponse):
        return await handle_send_task_response(task_response)

    if isinstance(task_response, SendTaskStreamingResponse):
        return await handle_streaming_response(task_response)

    logger.error(f"Unhandled task response type: {type(task_response)}")
    return {"status": "ignored"}


async def handle_send_task_response(task_response: SendTaskResponse):
    """
    Handles non-streaming task responses
    :param task_response: payload to handle
    """
    session_id = task_response.result.sessionId
    artifact = task_response.result.artifacts[0] if task_response.result.artifacts else None
    state = task_response.result.status.state

    await update_status(session_id, "generator", task_response)
    if state == TaskState.SUBMITTED:
        return {"status": "success"}

    return await send_artifact_to_websocket(session_id, artifact, state)


async def handle_streaming_response(task_response: SendTaskStreamingResponse):
    """
    Handles streaming responses
    :param task_response: payload to handle
    """
    result = task_response.result
    session_id = result.metadata.get("sessionId", "anonymous")
    artifact = result.artifact if isinstance(result, TaskArtifactUpdateEvent) else None
    state = getattr(result.status, "state", TaskState.UNKNOWN)

    await update_status(session_id, "generator", task_response)
    if state == TaskState.SUBMITTED:
        return {"status": "success"}

    return await send_artifact_to_websocket(session_id, artifact, state)


async def send_artifact_to_websocket(session_id: str, artifact: Artifact | None, state: TaskState):
    """
    Sends the html or file update to websocket
    """
    websocket = user_ui_bridges.get(session_id).generator_socket
    if not websocket:
        logger.warning(f"No connected generator socket found for session: {session_id}")
        return {"status": "success"}

    if not artifact or not artifact.parts:
        logger.warning(f"No artifact or parts to send for session: {session_id}")
        return {"status": "success"}

    main_part = artifact.parts[0]
    if isinstance(main_part, FilePart):
        await handle_file_part(main_part, websocket)
    elif isinstance(main_part, TextPart):
        await handle_text_part(main_part, state, session_id, websocket)
    else:
        logger.error(f"Unhandled part type: {type(main_part)}")

    return {"status": "success"}


async def handle_file_part(part: FilePart, websocket: WebSocket):
    """Download and store the image, then trigger a client reload."""
    response = await httpx.AsyncClient().get(part.file.uri)
    image = response.content
    images_dir = Path("images")
    images_dir.mkdir(parents=True, exist_ok=True)
    image_path = images_dir / part.file.name
    image_path.write_bytes(image)
    await websocket.send_text("__reload__")


async def handle_text_part(part: TextPart, state: TaskState, session_id: str, websocket: WebSocket):
    """Send text or completion notice depending on task state."""
    if state == TaskState.WORKING:
        logger.info(f"[{session_id}] Sending text: {part.text}")
        await websocket.send_text(part.text)
    elif state == TaskState.COMPLETED:
        logger.info(f"[{session_id}] Task completed.")
        await websocket.send_text("__completed__")


@app.post("/act")
async def act(payload: str = Body(...)):
    """
    Endpoint to run the Act Agent
    """
    logger.info(payload)
    response = await invoke_act_agent(payload)
    return response


current_file_dir = Path(__file__).parent
mount_chainlit(app=app, target=str(current_file_dir / "my_cl_app.py"), path="/chainlit")


@app.post("/echo")
async def echo(payload: dict = Body(...)):
    """
    Used for testing
    """
    logger.info(payload)
    return payload


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
