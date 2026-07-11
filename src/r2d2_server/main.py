from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="r2d2-server")

UI_DIR = Path(__file__).parent / "ui"

app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")


def home_page() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


app.add_api_route("/", home_page, methods=["GET"])
app.add_api_route("/home", home_page, methods=["GET"])


@app.get("/ping", tags=["health"])
async def ping() -> dict[str, str]:
    return {"status": "ok"}
