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
| `DELETE` | `/logs/{id}` | Bearer | Delete a single log entry |
| `GET` | `/x0art/docs` | — | Interactive Swagger UI |

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
- **Vanilla JS** — the dashboard is a single `static/index.html`, no build step
- **JSON Crack** — the detail modal's Diagram tab renders a React island
  ([jsoncrack-react](https://github.com/AykutSarac/jsoncrack.com)), prebuilt
  into `static/app/`

### The diagram island

The Diagram tab is the one part that is not hand-written vanilla JS: it mounts
the real `jsoncrack-react` component, because reproducing that graph layout by
hand was both slow and visually wrong.

The bundle is **committed** under `static/app/`, so running the app needs no
Node toolchain:

```bash
uv sync
API_KEY=your-secret-key uv run python main.py
```

You only need Node when you change the island itself:

```bash
cd frontend
npm install
npm run build      # writes ../static/app/
```

It is loaded lazily — the page costs nothing extra until you open the Diagram
tab for the first time. Graphs above 1,500 nodes show a fallback instead of
rendering.

## License

MIT
