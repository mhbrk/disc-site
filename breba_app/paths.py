from pathlib import Path

from starlette.templating import Jinja2Templates

app_path = Path(__file__).parent

templates = Jinja2Templates(directory=app_path / "templates")