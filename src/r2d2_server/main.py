import json
import os
from pathlib import Path
from typing import TypeGuard

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from r2d2_server import motor_controller, proximity_controller
from r2d2_server.camera_stream import CameraStreamError, stream_camera_frames
from r2d2_server.controller import Direction, RobotController
from r2d2_server.logging_config import configure_logging

app = FastAPI(title="r2d2-server")
logger = configure_logging()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("R2D2_CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

UI_DIR = Path(__file__).parent / "ui"
UI_API_BASE_URL_ENV = "R2D2_UI_API_BASE_URL"
VALID_DIRECTIONS: set[Direction] = {
    "forward",
    "backward",
    "left",
    "right",
    "rotate_cw",
    "rotate_ccw",
    "stop",
}

robot_controller = RobotController()


def home_page() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


def ui_config_script() -> Response:
    config = {"apiBaseUrl": os.getenv(UI_API_BASE_URL_ENV, "")}
    content = f"window.R2D2_CONFIG = {json.dumps(config)};\n"
    return Response(content=content, media_type="application/javascript")


app.add_api_route("/", home_page, methods=["GET"])
app.add_api_route("/home", home_page, methods=["GET"])
app.add_api_route("/ui/config.js", ui_config_script, methods=["GET"])
app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")


@app.get("/ping", tags=["health"])
async def ping() -> dict[str, str]:
    logger.info("http_request endpoint=/ping status=ok")
    return {"status": "ok"}


@app.get("/motor/status", tags=["health"])
async def motor_status() -> motor_controller.MotorStatus:
    status = motor_controller.get_status()
    logger.info(
        "http_request endpoint=/motor/status available=%s mode=%s",
        status["available"],
        status["mode"],
    )
    return status


@app.get("/proximity/status", tags=["health"])
async def proximity_status() -> proximity_controller.ProximityStatus:
    status = proximity_controller.get_status()
    logger.info(
        "http_request endpoint=/proximity/status available=%s mode=%s",
        status["available"],
        status["mode"],
    )
    return status


@app.websocket("/ws/movement")
async def movement_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("websocket_connected path=/ws/movement")
    await websocket.send_json(
        {
            "type": "connected",
            "direction": "stop",
            "motor": motor_controller.get_status(),
        },
    )

    try:
        while True:
            payload = await websocket.receive_json()
            logger.info("websocket_payload payload=%s", payload)
            response = handle_movement_payload(payload)
            await websocket.send_json(response)
    except WebSocketDisconnect:
        logger.info("websocket_disconnected path=/ws/movement")
        robot_controller.stop()


@app.websocket("/ws/proximity")
async def proximity_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("websocket_connected path=/ws/proximity")
    await websocket.send_json(
        {
            "type": "connected",
            "stream": "proximity",
            "status": proximity_controller.get_status(),
        },
    )

    try:
        async for reading in proximity_controller.stream_readings():
            await websocket.send_json(reading)
    except WebSocketDisconnect:
        logger.info("websocket_disconnected path=/ws/proximity")


@app.websocket("/ws/camera")
async def camera_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("websocket_connected path=/ws/camera")
    await websocket.send_json({"type": "connected", "stream": "camera"})

    try:
        async for frame in stream_camera_frames():
            await websocket.send_bytes(frame)
    except WebSocketDisconnect:
        logger.info("websocket_disconnected path=/ws/camera")
    except CameraStreamError as exc:
        logger.warning("camera_stream_error error=%s", exc)
        await websocket.send_json({"type": "error", "message": str(exc)})


def handle_movement_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        logger.warning("movement_payload_rejected reason=payload_not_object")
        return {
            "status": "error",
            "message": "Payload must be an object",
            "motor": motor_controller.get_status(),
        }

    raw_direction = payload.get("direction")
    if not is_valid_direction(raw_direction):
        logger.warning(
            "movement_payload_rejected reason=unsupported_direction direction=%s",
            raw_direction,
        )
        return {
            "status": "error",
            "message": "Unsupported movement direction",
            "motor": motor_controller.get_status(),
        }

    response = robot_controller.execute(raw_direction)
    return {**response, "motor": motor_controller.get_status()}


def is_valid_direction(value: object) -> TypeGuard[Direction]:
    return isinstance(value, str) and value in VALID_DIRECTIONS
