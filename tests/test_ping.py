from fastapi.testclient import TestClient

from r2d2_server.main import app

client = TestClient(app)


def test_ping_returns_ok() -> None:
    response = client.get("/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
