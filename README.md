# r2d2-server

FastAPI server for controlling a four-wheel R2D2 robot car from a browser UI.

The app serves a cockpit-style controller at `/` and `/home`, accepts movement
commands over WebSocket, and dispatches those commands to GPIO motor control
functions.

## Features

- Browser controller UI for keyboard and touch devices
- Keyboard controls: `W`, `A`, `S`, `D`, `Q`, `E`
- Touch controls: forward, backward, left, right, rotate CW, rotate CCW, stop
- WebSocket movement endpoint
- Motor status endpoint
- GPIO motor driver integration through `gpiozero`
- Server logs written to `logs/server.log`

## Controls

| Input | Direction |
| --- | --- |
| `W` | Forward |
| `S` | Backward |
| `A` | Left |
| `D` | Right |
| `Q` | Rotate clockwise |
| `E` | Rotate counterclockwise |

Touch buttons in the UI use the same movement commands as the keyboard.

## Motor Pins

The motor controller uses these GPIO pins:

| Name | GPIO |
| --- | --- |
| `IN1` | `17` |
| `IN2` | `27` |
| `IN3` | `22` |
| `IN4` | `23` |

On a Raspberry Pi with GPIO available, these pins are controlled with
`gpiozero.OutputDevice`.

On a non-Pi machine or when GPIO is unavailable, the server stays running and
uses no-op motor outputs. The UI shows `INACTIVE`, and `/motor/status` reports
the error.

## API

- `GET /`
  Serves the controller UI.

- `GET /home`
  Serves the same controller UI.

- `GET /ping`
  Returns:

  ```json
  {"status": "ok"}
  ```

- `GET /motor/status`
  Returns motor availability, mode, error, and pin mapping:

  ```json
  {
    "available": false,
    "mode": "noop",
    "error": "Unable to load any default pin factory!",
    "pins": {
      "IN1": 17,
      "IN2": 27,
      "IN3": 22,
      "IN4": 23
    }
  }
  ```

- `WS /ws/movement`
  Accepts movement payloads:

  ```json
  {"direction": "forward"}
  ```

  Supported directions:

  - `forward`
  - `backward`
  - `left`
  - `right`
  - `rotate_cw`
  - `rotate_ccw`
  - `stop`

  Responses include command status and motor status. If the motor driver or
  pins are unavailable, responses use `status: "inactive"`.

## Logs

Logs are written to:

```text
logs/server.log
```

The log directory can be changed with:

```bash
R2D2_LOG_DIR=/path/to/logs uv run uvicorn r2d2_server.main:app
```

## Development

Install dependencies:

```bash
uv sync --dev
```

Run the API locally:

```bash
uv run uvicorn r2d2_server.main:app --host 0.0.0.0 --port 8000 --reload
```

Open the controller:

```text
http://127.0.0.1:8000/
```

Run checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Install pre-commit hooks:

```bash
uv run pre-commit install
```
