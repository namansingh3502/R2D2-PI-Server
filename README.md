# r2d2-server

FastAPI service with a public health endpoint.

## Development

Install dependencies:

```bash
uv sync --dev
```

Run the API locally:

```bash
uv run uvicorn r2d2_server.main:app --reload
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

## API

- `GET /ping` returns `{"status": "ok"}` and requires no authentication.
