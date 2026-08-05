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


class LogEntryResponse(BaseModel):
    """A single log entry captured by the webhook receiver."""

    id: int = Field(..., description="Auto-incremented log entry ID")
    timestamp: str = Field(
        ..., description="UTC timestamp (ISO 8601) when the webhook was received"
    )
    ip_address: str = Field(
        ..., description="Originating IP address derived from the connection"
    )
    payload: Any = Field(
        ...,
        description="The full webhook payload. Can be any JSON value: object, string, array, number, boolean, or null.",
        json_schema_extra={
            "examples": [
                {"event": "deploy", "status": "success", "duration_ms": 1234},
                "Deployment completed successfully",
                [1, 2, 3, "note"],
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


class ExportData(BaseModel):
    """JSON export response containing all log entries."""

    export_date: str = Field(
        ..., description="UTC timestamp when the export was generated"
    )
    total: int = Field(..., description="Number of log entries in this export")
    items: list[LogEntryResponse] = Field(
        ..., description="Array of all log entries, newest first"
    )


class ImportResult(BaseModel):
    """Result of a log import operation."""

    imported: int = Field(
        ..., description="Number of log entries successfully imported"
    )


class DeleteResult(BaseModel):
    """Result of a log deletion operation."""

    deleted: bool = Field(..., description="Whether the log entry was deleted")
    id: int = Field(..., description="ID of the deleted log entry")


# ── Helper ──────────────────────────────────────────────────────────────────


def _parse_stored_payload(stored: str):
    """Try to parse a stored payload back to its original JSON type.
    Falls back to raw string if it wasn't valid JSON."""
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
    description="""HookView is a real-time webhook log receiver with SSE streaming, SQLite
persistence, file upload support, and a live browser dashboard. It accepts
**any** JSON payload — no schema or required fields.

## 🚀 Step-by-step tutorial

### Step 1 — Install and start the server

```bash
git clone https://github.com/x0art/hookview.git
cd hookview
uv sync
API_KEY=your-secret-key uv run python main.py
```

You should see the startup banner, and the server will listen on
**http://localhost:8000**. On Windows, set the key first with
`set API_KEY=your-secret-key` (cmd) or `$env:API_KEY = "your-secret-key"` (PowerShell).

### Step 2 — Open the live dashboard

Open **http://localhost:8000** in your browser, type `your-secret-key` into the
**Key** field, and click **Connect**. The status turns green and every incoming
webhook appears in the table in real time.

### Step 3 — Send your first webhook

```bash
curl -X POST http://localhost:8000/webhook \\
  -H "Authorization: Bearer your-secret-key" \\
  -H "Content-Type: application/json" \\
  -d '{"event": "deploy", "status": "success"}'
```

You get a `201 Created` response with the stored entry, and the dashboard
updates instantly.

### Step 4 — Try other payload types

HookView accepts any valid JSON value — object, string, array, number,
boolean, or `null`:

| Payload type | curl `-d` value |
|--------------|-----------------|
| Object       | `{"message": "hello"}` |
| String       | `"just a string"` |
| Array        | `[1, 2, 3, "mixed"]` |
| Number       | `42` |
| Boolean      | `true` |
| Null         | `null` |

### Step 5 — Send a webhook with a file

Use `multipart/form-data` to attach a file (up to 1 GB) alongside form fields:

```bash
curl -X POST http://localhost:8000/webhook \\
  -H "Authorization: Bearer your-secret-key" \\
  -F 'message=Deploy artifact' \\
  -F 'file=@./build.zip'
```

Form fields are bundled into the payload object, and the file is saved to
`uploads/` and linked from the dashboard.

### Step 6 — Watch the stream live

```bash
curl -N http://localhost:8000/stream \\
  -H "Authorization: Bearer your-secret-key"
```

You receive `event: connected` immediately, then an `event: log` push for
every new webhook.

## 🔑 Authentication

All endpoints require the Bearer API key set via the `API_KEY` environment
variable:

```
Authorization: Bearer <your-api-key>
```

Missing or invalid keys are rejected with `403`.

## 📚 Endpoint reference

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/webhook` | Send a webhook (JSON or multipart) |
| `GET` | `/stream` | Real-time SSE stream of new logs |
| `GET` | `/logs` | Paginated historical logs |
| `GET` | `/logs/export` | Download all logs as JSON |
| `POST` | `/logs/import` | Import logs from a JSON backup |
| `DELETE` | `/logs/{id}` | Delete a single log entry |

## 💡 Tips

- Every endpoint below can be tried right here with **Try it out**.
- The dashboard (`/`) has search, auto-scroll, export/import, and a built-in
  tester for sending test webhooks without leaving the browser.
    """,
    version="1.2.0",
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
            payload TEXT NOT NULL,
            filename TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    await db.commit()
    return db


# ── SSE Event Bus ──────────────────────────────────────────────────────────

# Each connected SSE client gets its own queue; broadcast() fans out to all
# of them so every client receives every event. (A single shared queue would
# hand each event to exactly one connection and silently starve the others.)
_clients: set[asyncio.Queue] = set()


async def broadcast(event: str, data: dict):
    """Push an SSE event to all connected clients."""
    for queue in list(_clients):
        queue.put_nowait({"event": event, "data": data})


async def event_generator():
    """Generator for SSE streaming."""
    queue: asyncio.Queue = asyncio.Queue()
    _clients.add(queue)
    try:
        # Send initial heartbeat to confirm connection
        yield {"event": "connected", "data": "SSE connection established"}

        while True:
            # Wait for the next event, then push it to this client
            item = await queue.get()
            yield {"event": item["event"], "data": json.dumps(item["data"])}
    finally:
        _clients.discard(queue)


# ── Endpoints ──────────────────────────────────────────────────────────────


@app.post(
    "/webhook",
    dependencies=[Depends(verify_auth)],
    response_model=LogEntryResponse,
    summary="Receive a webhook event",
    description="""Send a webhook event. The **entire** JSON body is stored as the log entry's
payload — there are no required fields and no schema to match.

## JSON request

```bash
curl -X POST http://localhost:8000/webhook \\
  -H "Authorization: Bearer your-secret-key" \\
  -H "Content-Type: application/json" \\
  -d '{"event": "deploy", "status": "success"}'
```

Any valid JSON value is accepted: object, string, array, number, boolean,
or `null`.

## Multipart request (with file)

```bash
curl -X POST http://localhost:8000/webhook \\
  -H "Authorization: Bearer your-secret-key" \\
  -F 'message=Deploy artifact' \\
  -F 'file=@./build.zip'
```

- **Any form fields** are bundled into a JSON payload object
- **`file`** (optional) — an uploaded file, max 1 GB, saved to `uploads/`

## Response

`201 Created` with the stored log entry:

```json
{
  "id": 42,
  "timestamp": "2026-08-05T12:34:56Z",
  "ip_address": "203.0.113.1",
  "payload": {"event": "deploy", "status": "success"},
  "filename": null
}
```

The entry is also broadcast over SSE, so open dashboards update instantly.
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
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "description": "Any valid JSON value — object, string, array, number, boolean, or null.",
                        "examples": [
                            {"event": "deploy", "status": "success"},
                            "simple string message",
                            [1, 2, 3],
                            42,
                            True,
                            None,
                        ],
                    },
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string",
                                "format": "binary",
                                "description": "Optional file attachment (max 1 GB). Saved to the uploads/ directory.",
                            },
                        },
                        "description": "Any form fields are stored as a JSON payload object. A file can be attached via the 'file' field.",
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
    payload = None

    content_type = request.headers.get("content-type", "").lower()

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        # Parse form data — bundle all fields into a JSON payload
        form = await request.form()
        form_dict = {}
        file: StarletteUploadFile | None = None

        for key in form:
            value = form.get(key)
            if isinstance(value, StarletteUploadFile):
                file = value
            elif isinstance(value, str):
                # Try to parse as JSON for flexibility
                try:
                    form_dict[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    form_dict[key] = value

        if file and file.filename:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="File too large")

            safe_name = f"{timestamp.replace(':', '-').replace('.', '-')}_{file.filename}"
            file_path = UPLOAD_DIR / safe_name
            file_path.write_bytes(content)
            saved_filename = safe_name

        payload = form_dict if form_dict else {}

    else:
        # Parse JSON body — accept any valid JSON value
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Serialize for storage: always JSON-encode for lossless round-tripping
    stored_payload = json.dumps(payload, ensure_ascii=False)

    # Insert into SQLite
    db = await aiosqlite.connect(str(DB_PATH))
    cursor = await db.execute(
        "INSERT INTO logs (timestamp, ip_address, payload, filename) VALUES (?, ?, ?, ?)",
        (timestamp, ip_address, stored_payload, saved_filename),
    )
    await db.commit()
    log_id = cursor.lastrowid
    await db.close()

    # Parse stored payload back to its original type for the response
    display_payload = _parse_stored_payload(stored_payload)

    # Build response entry
    log_entry = {
        "id": log_id,
        "timestamp": timestamp,
        "ip_address": ip_address,
        "payload": display_payload,
        "filename": saved_filename,
    }

    # Broadcast to SSE clients
    await broadcast("log", log_entry)

    return JSONResponse(content=log_entry, status_code=201)


@app.get(
    "/stream",
    dependencies=[Depends(verify_auth)],
    summary="Stream log entries in real-time (SSE)",
    description="""Opens a **Server-Sent Events** (SSE) connection that pushes new log entries
the moment they arrive.

## Watch live from the terminal

```bash
curl -N http://localhost:8000/stream \\
  -H "Authorization: Bearer your-secret-key"
```

## Events

| Event | Data | Description |
|-------|------|-------------|
| `connected` | string | Heartbeat confirming the connection |
| `log` | JSON | A new log entry |
| `delete` | JSON | An entry was deleted (`{"id": 42}`) |

The connection stays open indefinitely. The dashboard (`/`) uses this
endpoint to update the table in real time.
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
    description="""Returns a paginated list of historical log entries, **newest first**.

## Pagination

Use `limit` and `offset` for cursor-style paging:

| Call | Returns |
|------|---------|
| `/logs?limit=50&offset=0` | First 50 entries |
| `/logs?limit=50&offset=50` | Next 50 entries |

- `limit` — 1 to 1000 (default 50)
- `offset` — number of entries to skip (default 0)
- The response includes `total`, the overall count, so you know when to stop
  paging
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
        "SELECT id, timestamp, ip_address, payload, filename FROM logs ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = await cursor.fetchall()
    await db.close()

    items = [
        {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "ip_address": row["ip_address"],
            "payload": _parse_stored_payload(row["payload"]),
            "filename": row["filename"],
        }
        for row in rows
    ]

    return {"items": items, "total": total}


@app.get(
    "/logs/export",
    dependencies=[Depends(verify_auth)],
    response_model=ExportData,
    summary="Export all log entries as JSON",
    description="""Downloads **all** log entries as a JSON document, newest first, wrapped with
export metadata. Use it to back up your logs.

## Example

```bash
curl http://localhost:8000/logs/export \\
  -H "Authorization: Bearer your-secret-key" \\
  -o backup.json
```

The saved file can be restored later via `POST /logs/import`.
    """,
    tags=["Logs"],
    responses={
        200: {"description": "JSON export of all log entries"},
        403: {
            "model": ErrorResponse,
            "description": "Invalid or missing Bearer API key",
        },
    },
)
async def export_logs():
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row

    cursor = await db.execute(
        "SELECT id, timestamp, ip_address, payload, filename FROM logs ORDER BY id DESC"
    )
    rows = await cursor.fetchall()
    await db.close()

    items = [
        {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "ip_address": row["ip_address"],
            "payload": _parse_stored_payload(row["payload"]),
            "filename": row["filename"],
        }
        for row in rows
    ]

    return ExportData(
        export_date=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        total=len(items),
        items=items,
    )


@app.post(
    "/logs/import",
    dependencies=[Depends(verify_auth)],
    response_model=ImportResult,
    summary="Import log entries from JSON",
    description="""Imports log entries from a JSON array. Use it to restore a backup created
with `GET /logs/export`, or to seed data.

## Requirements

- The request body must be a **JSON array** of log entries
- Each entry needs `ip_address` and `payload` (`timestamp` defaults
  to the import time; `id` and `filename` are optional)

## JSON body example

```json
[
  {
    "timestamp": "2026-08-05T12:00:00Z",
    "ip_address": "203.0.113.1",
    "payload": {"event": "restored", "status": "ok"}
  }
]
```

## Upload a backup file

Send the same array as a file upload using the `file` field:

```bash
curl -X POST http://localhost:8000/logs/import \\
  -H "Authorization: Bearer your-secret-key" \\
  -F 'file=@backup.json'
```

Imported entries are broadcast over SSE so connected dashboards update live.
    """,
    tags=["Logs"],
    responses={
        200: {"description": "Import completed with count of imported entries"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid JSON or missing required fields",
        },
        403: {
            "model": ErrorResponse,
            "description": "Invalid or missing Bearer API key",
        },
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "timestamp": {
                                    "type": "string",
                                    "description": "ISO 8601 UTC timestamp",
                                    "example": "2026-07-27T12:34:56Z",
                                },
                                "ip_address": {
                                    "type": "string",
                                    "description": "Originating IP address",
                                    "example": "192.168.1.1",
                                },
                                "payload": {
                                    "description": "Any valid JSON value",
                                    "example": {"event": "deploy", "status": "success"},
                                },
                                "filename": {
                                    "type": "string",
                                    "description": "Optional uploaded filename",
                                    "nullable": True,
                                },
                            },
                            "required": ["timestamp", "ip_address", "payload"],
                        },
                    },
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string",
                                "format": "binary",
                                "description": "JSON file containing an array of log entries",
                            },
                        },
                    },
                },
            },
        },
    },
)
async def import_logs(request: Request):
    content_type = request.headers.get("content-type", "").lower()
    entries = None

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        file: StarletteUploadFile | None = None
        for key in form:
            value = form.get(key)
            if isinstance(value, StarletteUploadFile):
                file = value
                break
        if file:
            content = await file.read()
            try:
                decoded = content.decode("utf-8")
                entries = json.loads(decoded)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid JSON in uploaded file: {e}",
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="No file found in multipart upload. Attach a .json file as the 'file' field.",
            )
    else:
        try:
            body = await request.body()
            entries = json.loads(body) if body else None
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(entries, list):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a JSON array of log entries",
        )

    if not entries:
        return ImportResult(imported=0)

    db = await aiosqlite.connect(str(DB_PATH))
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    imported_count = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        timestamp = entry.get("timestamp", now)
        ip_address = entry.get("ip_address")
        payload_raw = entry.get("payload")
        filename = entry.get("filename")

        if not ip_address or payload_raw is None:
            continue

        stored_payload = json.dumps(payload_raw, ensure_ascii=False)

        cursor = await db.execute(
            "INSERT INTO logs (timestamp, ip_address, payload, filename) VALUES (?, ?, ?, ?)",
            (timestamp, str(ip_address), stored_payload, filename),
        )
        await db.commit()
        log_id = cursor.lastrowid
        imported_count += 1

        # Broadcast each imported entry via SSE
        display_payload = _parse_stored_payload(stored_payload)
        log_entry = {
            "id": log_id,
            "timestamp": timestamp,
            "ip_address": str(ip_address),
            "payload": display_payload,
            "filename": filename,
        }
        await broadcast("log", log_entry)

    await db.close()
    return ImportResult(imported=imported_count)


@app.delete(
    "/logs/{log_id}",
    dependencies=[Depends(verify_auth)],
    response_model=DeleteResult,
    summary="Delete a single log entry",
    description="""Deletes the log entry with the given ID. If the entry has an associated
uploaded file, the file is removed from `uploads/` as well. The deletion is
broadcast over SSE so all open dashboards remove the row instantly.

## Example

```bash
curl -X DELETE http://localhost:8000/logs/42 \\
  -H "Authorization: Bearer your-secret-key"
```

Returns `200` with `{"deleted": true, "id": 42}`.
    """,
    tags=["Logs"],
    responses={
        200: {"description": "Log entry deleted"},
        403: {
            "model": ErrorResponse,
            "description": "Invalid or missing Bearer API key",
        },
        404: {
            "model": ErrorResponse,
            "description": "Log entry not found",
        },
    },
)
async def delete_log(log_id: int):
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row

    cursor = await db.execute("SELECT filename FROM logs WHERE id = ?", (log_id,))
    row = await cursor.fetchone()
    if row is None:
        await db.close()
        raise HTTPException(status_code=404, detail=f"Log entry {log_id} not found")

    await db.execute("DELETE FROM logs WHERE id = ?", (log_id,))
    await db.commit()
    await db.close()

    # Remove the associated uploaded file, if any (best effort — the log row
    # is already deleted, so a locked file must not fail the request)
    filename = row["filename"]
    if filename:
        file_path = UPLOAD_DIR / filename
        try:
            if file_path.exists():
                file_path.unlink()
        except OSError:
            pass

    await broadcast("delete", {"id": log_id})
    return DeleteResult(deleted=True, id=log_id)


# ── Frontend ───────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
