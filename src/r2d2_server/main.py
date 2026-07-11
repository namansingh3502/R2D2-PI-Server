from pathlib import Path
from typing import TypeGuard

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from r2d2_server import motor_controller
from r2d2_server.controller import Direction, RobotController
from r2d2_server.logging_config import configure_logging

app = FastAPI(title="r2d2-server")
logger = configure_logging()

UI_DIR = Path(__file__).parent / "ui"
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

app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")


def home_page() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


app.add_api_route("/", home_page, methods=["GET"])
app.add_api_route("/home", home_page, methods=["GET"])


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
