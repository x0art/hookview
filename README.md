# HookView

Real-time webhook log receiver with SSE streaming, SQLite persistence,
file upload support, and a live browser UI.

[![GitHub](https://img.shields.io/badge/github-x0art/hookview-181717?style=flat&logo=github)](https://github.com/x0art/hookview)

## Quick Start

```bash
git clone https://github.com/x0art/hookview.git
cd hookview
uv sync                    # install dependencies
API_KEY=your-secret-key uv run python main.py
```

Open **http://localhost:8000** in your browser and enter your API key.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | — | Live log viewer UI |
| `POST` | `/webhook` | Bearer | Receive a webhook (JSON or multipart with file) |
| `GET` | `/stream` | Bearer | SSE real-time log stream |
| `GET` | `/logs` | Bearer | Paginated historical logs |
| `GET` | `/docs` | — | Interactive Swagger UI |

## Usage

### Send a webhook

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Authorization: Bearer your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"message": "Deploy completed!"}'
```

The `message` field accepts **any JSON type** — string, object, array, number, boolean, or null.

### With file upload

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Authorization: Bearer your-secret-key" \
  -F 'message=Deploy artifact' \
  -F 'file=@./build.zip'
```

### Stream live

```bash
curl -N http://localhost:8000/stream \
  -H "Authorization: Bearer your-secret-key"
```

## Configuration

| Env Var | Required | Description |
|---------|----------|-------------|
| `API_KEY` | ✅ | Bearer token for authentication |

## Tech Stack

- **FastAPI** — async Python web framework
- **SSE** — real-time streaming via `sse-starlette`
- **SQLite** — persistent storage with WAL mode
- **aiosqlite** — async SQLite driver
- **Vanilla JS** — no build tools needed, single-file frontend

## License

MIT
