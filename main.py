import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any, Optional

import aiosqlite
from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi.responses import JSONResponse, HTMLResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field


# ── Schema Models ────────────────────────────────────────────────────────────


class WebhookPayload(BaseModel):
    """
    Payload for the POST /webhook endpoint (JSON content type).

    The `message` field accepts **any valid JSON type**:
    - **string** — simple text message
    - **object** — structured event data
    - **array** — list of values
    - **number** — numeric payload
    - **boolean** — flag value
    - **null** — empty/null payload
    """

    model_config = {"extra": "forbid"}

    message: Any = Field(
        ...,
        description="The log message. Accepts any valid JSON type.",
        json_schema_extra={
            "examples": [
                "Deployment completed successfully",
                {"event": "deploy", "status": "success"},
                [1, 2, 3],
                42,
                True,
                None,
            ]
        },
    )


class LogEntryResponse(BaseModel):
    """A single log entry captured by the webhook receiver."""

    id: int = Field(..., description="Auto-incremented log entry ID")
    timestamp: str = Field(
        ..., description="UTC timestamp (ISO 8601) when the webhook was received"
    )
    ip_address: str = Field(
        ..., description="Originating IP address derived from the connection"
    )
    message: Any = Field(
        ...,
        description="The log message. Can be any JSON type: string, object, array, number, boolean, or null.",
        json_schema_extra={
            "examples": [
                "Deployment completed successfully",
                {"event": "deploy", "status": "success", "duration_ms": 1234},
                [1, 2, 3, "test"],
                42,
                True,
                None,
            ]
        },
    )
    filename: Optional[str] = Field(
        None, description="Uploaded filename if a file was included with the webhook"
    )


class LogListResponse(BaseModel):
    """Paginated list of log entries."""

    items: list[LogEntryResponse] = Field(..., description="Array of log entries")
    total: int = Field(..., description="Total number of log entries across all pages")


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(..., description="Human-readable error message")


# ── Helper ──────────────────────────────────────────────────────────────────


def _parse_stored_message(stored: str):
    """Try to parse a stored message back to its original JSON type.
    Falls back to raw string for backward compatibility with old entries."""
    try:
        return json.loads(stored)
    except (json.JSONDecodeError, TypeError):
        return stored


# ── App Setup ──────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db = await init_db()
    await db.close()

    border = "=" * 42
    print()
    print(border)
    print("  HookView - Log Receiver")
    print(f"  API_KEY: {API_KEY[:16]}...")
    print(f"  Webhook: POST /webhook")
    print(f"  Stream:  GET /stream")
    print(f"  Logs:    GET /logs")
    print(f"  Docs:    GET /docs")
    print(f"  Server:  http://0.0.0.0:8000")
    print(border)
    print()

    yield  # Server is running


app = FastAPI(
    title="HookView",
    description="""
A real-time webhook log receiver with SSE streaming, SQLite persistence,
file upload support, and a live browser UI.

## Authentication

All endpoints require a Bearer token set via the `API_KEY` environment variable.
Include it in requests as:
```
Authorization: Bearer <your-api-key>
```

## Message Types

The `message` field in a webhook payload is **not limited to strings** —
it accepts any valid JSON value:

| Type     | Example                                   |
|----------|-------------------------------------------|
| string   | `"Deployment completed"`                  |
| object   | `{"event": "deploy", "status": "ok"}`      |
| array    | `[1, 2, 3, "note"]`                       |
| number   | `42`                                      |
| boolean  | `true`                                    |
| null     | `null`                                    |

## Content Types

The webhook endpoint accepts **both** `application/json` and `multipart/form-data`.
Use multipart when you need to upload a file alongside the message.
    """,
    version="1.0.0",
    lifespan=lifespan,
    contact={
        "name": "HookView",
        "url": "https://github.com/x0art/hookview",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth ───────────────────────────────────────────────────────────────────

API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    print("FATAL: API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)


async def verify_auth(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[len("Bearer "):] != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# ── OpenAPI Security Scheme ────────────────────────────────────────────────


original_openapi = app.openapi


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = original_openapi()
    schema.setdefault("components", {}).setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "API key",
    }
    schema.setdefault("security", []).append({"BearerAuth": []})
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi


# ── Database ───────────────────────────────────────────────────────────────

DB_PATH = Path("data/logs.db")
UPLOAD_DIR = Path("uploads")
MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1 GB


async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    db = await aiosqlite.connect(str(DB_PATH))
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            message TEXT NOT NULL,
            filename TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    await db.commit()
    return db


# ── SSE Event Bus ──────────────────────────────────────────────────────────

_broadcast_queue: asyncio.Queue = asyncio.Queue()


async def broadcast(log_entry: dict):
    """Push a log entry to all connected SSE clients."""
    await _broadcast_queue.put(log_entry)


async def event_generator():
    """Generator for SSE streaming."""
    try:
        # Send initial heartbeat to confirm connection
        yield {"event": "connected", "data": "SSE connection established"}

        while True:
            # Wait for new log entry (blocks until one is available)
            log_entry = await _broadcast_queue.get()
            yield {"event": "log", "data": json.dumps(log_entry)}
    except asyncio.CancelledError:
        pass


# ── Endpoints ──────────────────────────────────────────────────────────────


@app.post(
    "/webhook",
    dependencies=[Depends(verify_auth)],
    response_model=LogEntryResponse,
    summary="Receive a webhook event",
    description="""
Accepts a webhook payload as either **JSON** or **multipart/form-data**.

## JSON request

```json
{"message": "Deploy completed"}
```

`message` accepts any JSON type — see the schema below for examples.

## Multipart request

Send as `multipart/form-data` with:
- **message** (required) — the log message string
- **file** (optional) — an uploaded file (max 1 GB)

The response mirrors the same structure as the JSON endpoint.
    """,
    tags=["Webhook"],
    responses={
        201: {"description": "Log entry created and broadcast via SSE"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid JSON body (not parsable)",
        },
        403: {
            "model": ErrorResponse,
            "description": "Invalid or missing Bearer API key",
        },
        413: {
            "model": ErrorResponse,
            "description": "Uploaded file exceeds the 1 GB limit",
        },
        422: {
            "model": ErrorResponse,
            "description": "Validation error — see detail for specifics",
        },
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": WebhookPayload.model_json_schema(),
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["message"],
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "The log message. Will be parsed as JSON if possible, otherwise treated as a raw string.",
                            },
                            "file": {
                                "type": "string",
                                "format": "binary",
                                "description": "Optional file attachment (max 1 GB). Saved to the uploads/ directory.",
                            },
                        },
                    },
                },
            },
            "required": True,
        },
    },
)
async def receive_webhook(request: Request):
    ip_address = request.client.host
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    saved_filename = None
    message = None

    content_type = request.headers.get("content-type", "").lower()

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        # Parse form data (multipart with optional file)
        form = await request.form()
        raw_message = form.get("message")
        file: StarletteUploadFile | None = form.get("file")

        if raw_message is None:
            raise HTTPException(status_code=422, detail="message field is required")

        if file and file.filename:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="File too large")

            safe_name = f"{timestamp.replace(':', '-').replace('.', '-')}_{file.filename}"
            file_path = UPLOAD_DIR / safe_name
            file_path.write_bytes(content)
            saved_filename = safe_name

        # Form values are always strings; try to parse as JSON for flexibility
        try:
            message = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            message = raw_message
    else:
        # Parse JSON body
        try:
            body = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="Request body must be a JSON object")

        if "message" not in body:
            raise HTTPException(status_code=422, detail="message field is required")

        message = body["message"]

    # Serialize for storage: always JSON-encode for lossless round-tripping
    stored_message = json.dumps(message, ensure_ascii=False)

    # Insert into SQLite
    db = await aiosqlite.connect(str(DB_PATH))
    cursor = await db.execute(
        "INSERT INTO logs (timestamp, ip_address, message, filename) VALUES (?, ?, ?, ?)",
        (timestamp, ip_address, stored_message, saved_filename),
    )
    await db.commit()
    log_id = cursor.lastrowid
    await db.close()

    # Parse stored message back to its original JSON type for the response
    display_message = _parse_stored_message(stored_message)

    # Build response entry
    log_entry = {
        "id": log_id,
        "timestamp": timestamp,
        "ip_address": ip_address,
        "message": display_message,
        "filename": saved_filename,
    }

    # Broadcast to SSE clients
    await broadcast(log_entry)

    return JSONResponse(content=log_entry, status_code=201)


@app.get(
    "/stream",
    dependencies=[Depends(verify_auth)],
    summary="Stream log entries in real-time (SSE)",
    description="""
Opens a **Server-Sent Events** (SSE) connection that pushes new log entries
as they arrive from the webhook endpoint.

### Event types

| Event       | Description                              |
|-------------|------------------------------------------|
| `connected` | Initial heartbeat confirming connection  |
| `log`       | A new log entry (data is JSON-encoded)   |

### Example (curl)

```bash
curl -N http://localhost:8000/stream \\
  -H "Authorization: Bearer <your-api-key>"
```
    """,
    tags=["Stream"],
    responses={
        200: {
            "description": "SSE event stream. Returns `text/event-stream` content type.",
        },
        403: {
            "model": ErrorResponse,
            "description": "Invalid or missing Bearer API key",
        },
    },
)
async def stream_logs():
    return EventSourceResponse(event_generator())


@app.get(
    "/logs",
    dependencies=[Depends(verify_auth)],
    response_model=LogListResponse,
    summary="Retrieve historical log entries",
    description="""
Returns a paginated list of log entries ordered by most recent first.

Use `limit` and `offset` for cursor-style pagination:
```
GET /logs?limit=10&offset=0   # first 10 entries
GET /logs?limit=10&offset=10  # next 10 entries
```
    """,
    tags=["Logs"],
    responses={
        200: {"description": "Paginated list of log entries"},
        403: {
            "model": ErrorResponse,
            "description": "Invalid or missing Bearer API key",
        },
    },
)
async def get_logs(
    limit: int = Query(
        default=50,
        ge=1,
        le=1000,
        description="Maximum number of log entries to return (1–1000)",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of entries to skip for pagination",
    ),
):
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row

    cursor = await db.execute("SELECT COUNT(*) as total FROM logs")
    row = await cursor.fetchone()
    total = row["total"] if row else 0

    cursor = await db.execute(
        "SELECT id, timestamp, ip_address, message, filename FROM logs ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = await cursor.fetchall()
    await db.close()

    items = [
        {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "ip_address": row["ip_address"],
            "message": _parse_stored_message(row["message"]),
            "filename": row["filename"],
        }
        for row in rows
    ]

    return {"items": items, "total": total}


# ── Frontend ───────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
