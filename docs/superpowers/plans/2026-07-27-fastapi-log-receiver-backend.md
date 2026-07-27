# FastAPI Log Receiver Backend Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI server that receives webhooks (with optional file uploads), persists logs to SQLite, and streams them live via SSE.

**Architecture:** Single Uvicorn worker with in-process `asyncio.Queue` for SSE broadcasting, SQLite with WAL mode for persistence, Bearer token auth from `API_KEY` env var.

**Tech Stack:** Python 3.12+, FastAPI, Uvicorn, sse-starlette, aiosqlite, python-multipart

## Global Constraints

- Python >= 3.12
- Single-file backend in `main.py`
- Uses `uv` as package manager (pyproject.toml)
- API key from `API_KEY` env var only (no default)
- SQLite WAL mode enabled
- Max file upload: 1 GB
- All endpoints require Bearer auth
- `message` field required on webhook
- `ip_address` derived from `request.client.host`

---

### Task 1: Update pyproject.toml and project scaffolding

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `uploads/.gitkeep` (placeholder to track directory)
- Create: `data/.gitkeep` (placeholder to track directory)

- [ ] **Step 1: Update pyproject.toml with dependencies**

```toml
[project]
name = "fastapi-log-receiver"
version = "0.1.0"
description = "Real-time FastAPI webhook receiver with SSE streaming and SQLite persistence"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sse-starlette>=2.0.0",
    "aiosqlite>=0.20.0",
    "python-multipart>=0.0.18",
]
```

- [ ] **Step 2: Update .gitignore**

```
# Byte-compiled
__pycache__/
*.py[cod]
*$py.class

# Virtual environment
.venv/
venv/

# Database
*.db
*.db-journal
*.db-wal
*.db-shm

# Uploads (keep directory, ignore files)
uploads/*
!uploads/.gitkeep

# Data directory (keep directory, ignore db)
data/*
!data/.gitkeep

# IDE
.vscode/
.idea/
```

- [ ] **Step 3: Create gitkeep placeholders**

```bash
mkdir -p uploads data && touch uploads/.gitkeep data/.gitkeep
```

### Task 2: Implement main.py — the FastAPI server

**Files:**
- Modify: `main.py`

**Interfaces:**
- Produces: FastAPI app instance, `POST /webhook`, `GET /stream`, `GET /logs`, auth dependency

- [ ] **Step 1: Write imports, app setup, and auth logic**

```python
import os
import sys
import time
import uuid
import json
import asyncio
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import aiosqlite
from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

# ── App Setup ──────────────────────────────────────────────────────────────

app = FastAPI(title="FastAPI Log Receiver")

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

# ── Database ───────────────────────────────────────────────────────────────

DB_PATH = Path("data/logs.db")
UPLOAD_DIR = Path("uploads")
MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1 GB

async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    db = await aiosqlite.connect(str(DB_PATH))
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            message TEXT NOT NULL,
            filename TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    await db.commit()
    return db

# ── SSE Event Bus ──────────────────────────────────────────────────────────

# Each connected SSE client gets its own asyncio.Event, stored here.
# We fan-out by iterating all events and setting them when a new log arrives.
_listeners: dict[str, asyncio.Event] = {}
_broadcast_queue: asyncio.Queue = asyncio.Queue()

async def broadcast(log_entry: dict):
    """Push a log entry to all connected SSE clients."""
    await _broadcast_queue.put(log_entry)

async def event_generator():
    """Generator for SSE streaming."""
    listener_id = str(uuid.uuid4())
    event = asyncio.Event()
    _listeners[listener_id] = event
    
    try:
        # Send initial heartbeat to confirm connection
        yield {"event": "connected", "data": "SSE connection established"}
        
        while True:
            # Wait for new data
            await event.wait()
            event.clear()
            
            # Drain all available items from the queue for this listener
            # The queue is shared, so we check for new items
            while not _broadcast_queue.empty():
                log_entry = await _broadcast_queue.get()
                yield {"event": "log", "data": json.dumps(log_entry)}
    except asyncio.CancelledError:
        pass
    finally:
        _listeners.pop(listener_id, None)

# ── Startup ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    db = await init_db()
    await db.close()
    
    print()
    print("╔══════════════════════════════════════╗")
    print("║  FastAPI Log Receiver                ║")
    print("║──────────────────────────────────────║")
    print(f"║  API_KEY: {API_KEY[:16]}...")
    print("║  Webhook: POST /webhook              ║")
    print("║  Stream:  GET /stream                ║")
    print("║  Logs:    GET /logs                  ║")
    print("║  Server:  http://0.0.0.0:8000        ║")
    print("╚══════════════════════════════════════╝")
    print()
```

- [ ] **Step 2: Write the webhook endpoint**

```python
@app.post("/webhook", dependencies=[Depends(verify_auth)])
async def receive_webhook(
    request: Request,
    message: str = Form(...),
    file: UploadFile = File(None),
):
    ip_address = request.client.host
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    saved_filename = None

    # Handle file upload
    if file and file.filename:
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        
        # Sanitize filename and save
        safe_name = f"{timestamp.replace(':', '-').replace('.', '-')}_{file.filename}"
        file_path = UPLOAD_DIR / safe_name
        content = await file.read()
        file_path.write_bytes(content)
        saved_filename = safe_name

    # Insert into SQLite
    db = await aiosqlite.connect(str(DB_PATH))
    cursor = await db.execute(
        "INSERT INTO logs (timestamp, ip_address, message, filename) VALUES (?, ?, ?, ?)",
        (timestamp, ip_address, message, saved_filename),
    )
    await db.commit()
    log_id = cursor.lastrowid
    await db.close()

    # Build response entry
    log_entry = {
        "id": log_id,
        "timestamp": timestamp,
        "ip_address": ip_address,
        "message": message,
        "filename": saved_filename,
    }

    # Broadcast to SSE clients
    await broadcast(log_entry)

    return JSONResponse(content=log_entry, status_code=201)
```

- [ ] **Step 3: Write the SSE stream endpoint**

```python
@app.get("/stream", dependencies=[Depends(verify_auth)])
async def stream_logs():
    return EventSourceResponse(event_generator())
```

- [ ] **Step 4: Write the logs history endpoint**

```python
@app.get("/logs", dependencies=[Depends(verify_auth)])
async def get_logs(
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
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
            "message": row["message"],
            "filename": row["filename"],
        }
        for row in rows
    ]
    
    return {"items": items, "total": total}
```

- [ ] **Step 5: Write the main entrypoint**

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Task 3: Install dependencies and verify server starts

- [ ] **Step 1: Install dependencies with uv**

```bash
cd /path/to/project && uv sync
```

- [ ] **Step 2: Set API_KEY and start server**

```bash
cd /path/to/project && set API_KEY=test-key-123 && uv run python main.py
```

Expected: Server prints the startup banner and waits for connections.

- [ ] **Step 3: Test webhook endpoint with curl (in a new terminal)**

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Authorization: Bearer test-key-123" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from webhook!"}'
```

Expected: Returns 201 with the log entry JSON.

- [ ] **Step 4: Test logs history endpoint**

```bash
curl http://localhost:8000/logs \
  -H "Authorization: Bearer test-key-123"
```

Expected: Returns the webhook log in the items array.

- [ ] **Step 5: Test auth rejection**

```bash
curl http://localhost:8000/logs \
  -H "Authorization: Bearer wrong-key"
```

Expected: Returns 403.

- [ ] **Step 6: Test SSE stream**

```bash
curl -N http://localhost:8000/stream \
  -H "Authorization: Bearer test-key-123"
```

Expected: Receives `event: connected` then waits. Sending another webhook should show a `event: log` push.
