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
- WebSocket camera stream endpoint
- WebSocket proximity sensor endpoint
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

## Proximity Sensor Pins

The robot uses two HC-SR04 ultrasonic sensors through `gpiozero.DistanceSensor`.
The physical sensors are currently swapped, so the server maps the right-side
GPIO pair to logical `left` and the left-side GPIO pair to logical `right`:

| Logical side | TRIG GPIO | ECHO GPIO |
| --- | --- | --- |
| `left` | `13` | `19` |
| `right` | `5` | `6` |

Wire ECHO through a voltage divider before connecting it to the Raspberry Pi
GPIO input.

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

- `GET /proximity/status`
  Returns proximity sensor availability, mode, error, and pin mapping:

  ```json
  {
    "available": true,
    "mode": "gpio",
    "error": null,
    "pins": {
      "left": {"trigger": 13, "echo": 19},
      "right": {"trigger": 5, "echo": 6}
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

- `WS /ws/proximity`
  Streams proximity readings in centimeters:

  ```json
  {
    "type": "proximity",
    "left_cm": 12.3,
    "right_cm": 45.6
  }
  ```

- `WS /ws/camera`
  Starts the Pi camera stream when a client connects. The endpoint sends an
  initial JSON connection message, then binary JPEG frames. By default it runs:

  ```bash
  rpicam-vid --codec mjpeg --timeout 0 --width 640 --height 480 --framerate 15 --output -
  ```

  Override the camera command with `R2D2_CAMERA_COMMAND` if the Pi camera setup
  uses a different capture command.

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

Create local environment config:

```bash
cp .env.example .env
```

Run the API locally:

```bash
uv run uvicorn r2d2_server.main:app --host 0.0.0.0 --port 8000 --reload
```

Run the local UI against a robot server on the network:

```bash
uv run uvicorn r2d2_server.main:app --host 127.0.0.1 --port 8000 --env-file .env
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

## Production Setup

Production uses Uvicorn supervised by Supervisor, with Nginx as the reverse
proxy.

Included config files:

- `conf/supervisor.conf`
- `conf/nginx.conf`
- `conf/uvicorn.env`

Install project dependencies on the host:

```bash
uv sync --no-dev
```

Run the app process directly with Uvicorn:

```bash
uv run --no-dev uvicorn r2d2_server.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1 --env-file conf/uvicorn.env
```

For Supervisor, copy or symlink the config:

```bash
sudo ln -s /home/naman/Desktop/R2D2-PI-Server/conf/supervisor.conf /etc/supervisor/conf.d/r2d2-server.conf
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status r2d2-server
```

For Nginx, copy or symlink the config:

```bash
sudo ln -s /home/naman/Desktop/R2D2-PI-Server/conf/nginx.conf /etc/nginx/conf.d/r2d2-server.conf
sudo nginx -t
sudo systemctl reload nginx
```

Nginx listens on port `80` and proxies to Uvicorn on `127.0.0.1:8000`,
including WebSocket upgrades for `/ws/movement`, `/ws/proximity`, and
`/ws/camera`.

Open the controller through Nginx:

```text
http://127.0.0.1/
```

Supervisor stdout/stderr logs are written under `logs/`, and app logs are
written to:

```text
logs/server.log
```

On Raspberry Pi, make sure the Supervisor `user` has permission to access the
GPIO backend. Without GPIO access, `/motor/status` reports inactive/noop mode
and the UI shows `INACTIVE`.
