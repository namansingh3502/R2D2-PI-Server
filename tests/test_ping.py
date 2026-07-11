from fastapi.testclient import TestClient

from r2d2_server import motor_controller
from r2d2_server.logging_config import LOG_FILE
from r2d2_server.main import app, robot_controller

client = TestClient(app)


def test_ping_returns_ok() -> None:
    response = client.get("/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_motor_status_returns_availability() -> None:
    motor_controller.set_motor_available_for_testing(False)

    response = client.get("/motor/status")

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["mode"] == "noop"
    motor_controller.set_motor_available_for_testing(True)


def test_home_page_is_served_at_root_and_home() -> None:
    for path in ("/", "/home"):
        response = client.get(path)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "CTRL::REMOTE" in response.text
        assert "/ui/styles.css" in response.text
        assert "/ui/app.js" in response.text


def test_ui_static_assets_are_served() -> None:
    response = client.get("/ui/app.js")

    assert response.status_code == 200
    assert "ROTATE CCW" in response.text
    assert "/ws/movement" in response.text
    assert "/motor/status" in response.text


def test_movement_websocket_dispatches_direction() -> None:
    motor_controller.set_motor_available_for_testing(True)

    with client.websocket_connect("/ws/movement") as websocket:
        connected = websocket.receive_json()
        assert connected["type"] == "connected"
        assert connected["direction"] == "stop"
        assert connected["motor"]["available"] is True

        websocket.send_json({"direction": "forward"})
        response = websocket.receive_json()

        assert response["status"] == "accepted"
        assert response["direction"] == "forward"
        assert str(robot_controller.current_direction) == "forward"

        websocket.send_json({"direction": "stop"})
        response = websocket.receive_json()

        assert response["status"] == "accepted"
        assert response["direction"] == "stop"
        assert str(robot_controller.current_direction) == "stop"


def test_movement_websocket_rejects_invalid_direction() -> None:
    with client.websocket_connect("/ws/movement") as websocket:
        websocket.receive_json()

        websocket.send_json({"direction": "jump"})
        response = websocket.receive_json()

        assert response["status"] == "error"
        assert response["message"] == "Unsupported movement direction"
        assert "motor" in response


def test_movement_websocket_reports_inactive_motor() -> None:
    motor_controller.set_motor_available_for_testing(False)

    with client.websocket_connect("/ws/movement") as websocket:
        websocket.receive_json()

        websocket.send_json({"direction": "forward"})
        response = websocket.receive_json()

        assert response["status"] == "inactive"
        assert response["direction"] == "forward"
        assert response["motor"]["available"] is False
    motor_controller.set_motor_available_for_testing(True)


def test_server_logs_movement_commands() -> None:
    motor_controller.set_motor_available_for_testing(True)
    robot_controller.execute("left")

    assert LOG_FILE.exists()
    assert "movement_command direction=left status=accepted" in LOG_FILE.read_text()
