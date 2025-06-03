import logging
import os
from pathlib import Path

from chainlit.utils import mount_chainlit
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Home page route
    """
    # Hardcode to simulate a user logging in
    session_id = "user-1-session-1"
    request.session["sessionId"] = session_id
    logger.info(f"Added ui bridge for session_id: {session_id}")

    logger.info(f"Session ID: {request.session.get('sessionId')}")
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

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
