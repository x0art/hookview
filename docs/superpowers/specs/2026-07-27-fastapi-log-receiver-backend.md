# FastAPI Log Receiver — Backend Design Spec

**Date:** 2026-07-27
**Status:** Draft

## Overview

A FastAPI-based real-time webhook receiver that ingests incoming HTTP requests (with optional file uploads), persists them to SQLite, and broadcasts them live to connected clients via Server-Sent Events (SSE).

## Architecture

```
[External Sender] ──POST /webhook──► [FastAPI Server] ──► [SQLite (WAL)]
                                      │                      │
                                      ├──► [asyncio.Queue]   │
                                      │         │            │
                                      │         ▼            │
                                      │   [SSE Broadcast]    │
                                      │         │            │
                                      ▼         ▼            ▼
                                 [Client A] [Client B]   [GET /logs]
```

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Worker model | Single Uvicorn worker | `asyncio.Queue` is in-process only; single worker avoids cross-process queue complexity |
| SQLite mode | WAL (Write-Ahead Logging) | Allows concurrent reads during writes, avoids lock contention |
| Real-time transport | SSE (`sse-starlette`) | Native HTTP, one-direction persistent connection, simpler than WebSockets for this use case |
| History fallback | `GET /logs` endpoint | Clients fetch history on connect, then switch to SSE for live updates |
| File upload max | 1 GB | User requirement |
| Auth | Single Bearer token from `API_KEY` env var | Simple, no admin endpoints needed |

## Endpoints

### `POST /webhook`
**Auth:** Bearer token required
**Content-Type:** `application/json` or `multipart/form-data`

Receive a webhook event. The server records:
- `timestamp` — server clock at reception (ISO 8601)
- `ip_address` — derived from `request.client.host` (not user-supplied)
- `message` — required string from the JSON body or form field
- `filename` — if a file was uploaded, the saved filename

**JSON request body:**
```json
{
  "message": "Deploy completed successfully"
}
```

**Multipart request:**
- Field `message` (required): string
- File `file` (optional): any file type, up to 1 GB

**Response (201):**
```json
{
  "id": 42,
  "timestamp": "2026-07-27T12:34:56.789Z",
  "ip_address": "203.0.113.1",
  "message": "Deploy completed successfully",
  "filename": null
}
```

**Error (422):** If `message` is missing or empty.

### `GET /stream`
**Auth:** Bearer token required

Server-Sent Events endpoint. Opens a persistent connection and pushes each new log entry as an SSE event as soon as it's received.

**SSE event format:**
```
data: {"id":42,"timestamp":"2026-07-27T12:34:56.789Z","ip_address":"203.0.113.1","message":"Deploy completed successfully","filename":null}

```

The connection stays open indefinitely. On client disconnect, clean up happens via `asyncio.CancelledError`.

### `GET /logs`
**Auth:** Bearer token required

Fetch historical log entries with optional pagination.

**Query parameters:**
- `limit` (int, default=50, max=1000): number of entries
- `offset` (int, default=0): pagination offset

**Response (200):**
```json
{
  "items": [
    {
      "id": 42,
      "timestamp": "2026-07-27T12:34:56.789Z",
      "ip_address": "203.0.113.1",
      "message": "Deploy completed successfully",
      "filename": null
    }
  ],
  "total": 150
}
```

## Data Model

### SQLite Table: `logs`

```sql
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    message TEXT NOT NULL,
    filename TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

PRAGMA: `journal_mode=WAL`

## Auth Middleware

A FastAPI `Depends()` function checks the `Authorization` header:

```
Authorization: Bearer <api-key>
```

The expected key is read from the `API_KEY` environment variable at startup. If the env var is not set, the server prints an error and exits with code 1.

## File Storage

- Uploaded files are saved to `./uploads/` directory
- Filename format: `{timestamp}_{original_filename}` (collision-safe)
- Directory auto-created on startup if missing
- No auto-cleanup (user manages manually)

## Startup Behavior

On startup, the server:
1. Validates `API_KEY` env var is present, exits with error if missing
2. Creates `./data/` and `./uploads/` directories if they don't exist
3. Initializes SQLite database at `./data/logs.db` with WAL mode and `logs` table
4. Prints a startup banner:

```
╔══════════════════════════════════════╗
║  FastAPI Log Receiver                ║
║──────────────────────────────────────║
║  API_KEY: sk-abc123def456...         ║
║  Webhook: POST /webhook              ║
║  Stream:  GET /stream                ║
║  Logs:    GET /logs                  ║
║  Server:  http://0.0.0.0:8000        ║
╚══════════════════════════════════════╝
```

## Dependencies

```toml
[project]
name = "fastapi-log-receiver"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sse-starlette>=2.0.0",
    "aiosqlite>=0.20.0",
    "python-multipart>=0.0.18",
]
```

## Error Handling

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Missing/empty `message` | 422 | `{"detail": "message field is required"}` |
| Missing/invalid API key | 403 | `{"detail": "Invalid or missing API key"}` |
| File too large (over 1 GB) | 413 | `{"detail": "File too large"}` |
| Method not allowed | 405 | Standard FastAPI 405 |

## File Structure

```
fastapi-log-receiver/
├── main.py              # FastAPI app (all backend logic)
├── pyproject.toml       # uv-managed dependencies
├── data/                # SQLite database directory (auto-created)
├── uploads/             # Uploaded files directory (auto-created)
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-07-27-fastapi-log-receiver-backend.md
├── .gitignore
└── README.md
```
