import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import chainlit as cl
from chainlit.auth import get_current_user
from chainlit.utils import mount_chainlit
from fastapi import FastAPI, Request, Depends
from fastapi import Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from breba_app.auth import change_password
from breba_app.config import init_db
from breba_app.generator_agent.agent import agent
from breba_app.paths import app_path, templates

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))


@asynccontextmanager
async def lifespan(app):
    await init_db()
    pat = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    await agent.ensure_initialized(pat)
    yield
    await agent.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compute static asset version based on max mtime of public files on startup
public_dir = app_path / "public"
if public_dir.exists():
    mtimes = [f.stat().st_mtime for f in public_dir.rglob('*') if f.is_file()]
    ASSET_VERSION = str(int(max(mtimes))) if mtimes else "1"
else:
    ASSET_VERSION = "1"


def asset_url(filename):
    base = f"/public/{filename}"
    return f"{base}?v={ASSET_VERSION}"


templates.env.globals['asset'] = asset_url

app.mount("/public",
          StaticFiles(directory=app_path / "public"),
          name="public")


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/public/favicon.ico")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Home page route.
    If cookie "X-Chainlit-Session-id" is set, render home.html
    otherwise render app.html
    """
    session_cookie = request.cookies.get("X-Chainlit-Session-id")

    if session_cookie:
        # Cookie missing → render app.html
        return templates.TemplateResponse("app.html", {"request": request})
    else:
        # Cookie exists → render home.html
        return templates.TemplateResponse("home.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    """
    Home page route. This just renders the HTML. All communication with the server is done through chianlit.
    """
    return templates.TemplateResponse("app.html", {"request": request})


@app.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    """
    Home page route. This just renders the HTML. All communication with the server is done through chianlit.
    """
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})


@app.post("/settings/account/password")
async def change_password_route(
        request: Request,
        current_user: Annotated[
            cl.User, Depends(get_current_user)
        ],
        current_password: str = Form(...),
        new_password: str = Form(...),
        confirm_password: str = Form(...),
):
    user_id = current_user.identifier

    if new_password != confirm_password:
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "error": "New passwords do not match.",
            },
            status_code=400
        )

    success = await change_password(user_id, current_password, new_password)

    if not success:
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "error": "Current password is incorrect.",
            },
            status_code=400
        )

    return RedirectResponse(url="/settings?success=1", status_code=303)


current_file_dir = Path(__file__).parent
mount_chainlit(app=app, target=str(current_file_dir / "my_cl_app.py"), path="/chainlit")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
