import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

from chainlit.context import init_ws_context
from chainlit.session import WebsocketSession
from chainlit.utils import mount_chainlit
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from common.storage import read_image_from_private
from config import init_db

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))


@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

IMAGE_DIR = Path("./images")


@app.api_route("/images/{file_path:path}", methods=["GET", "HEAD"])
async def custom_static_handler(file_path: str, request: Request):
    session_id = request.cookies.get("X-Chainlit-Session-id")
    print("Session ID:", session_id)

    ws_session = WebsocketSession.get_by_id(session_id=session_id)
    init_ws_context(ws_session)

    image_bytes = read_image_from_private(session_id=session_id, image_name=file_path)

    if not image_bytes:
        raise HTTPException(status_code=404, detail="File not found")

    # Guess MIME type from filename
    media_type, _ = mimetypes.guess_type(file_path)
    media_type = media_type or "application/octet-stream"

    headers = {
        "Content-Type": media_type,
        "Content-Length": str(len(image_bytes)),
    }

    if request.method == "HEAD":
        return Response(status_code=200, headers=headers)

    return Response(content=image_bytes, media_type=media_type, headers=headers)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Home page route. This just renders the HTML. All communication with the server is done through chianlit.
    """
    return templates.TemplateResponse("base.html", {"request": request})


# @app.post("/act")
# async def act(payload: str = Body(...)):
#     """
#     Endpoint to run the Act Agent
#     """
#     logger.info(payload)
#     response = await invoke_act_agent(payload)
#     return response


current_file_dir = Path(__file__).parent
mount_chainlit(app=app, target=str(current_file_dir / "my_cl_app.py"), path="/chainlit")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
