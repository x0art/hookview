"""Export/import round-trip, multi-database switching, and upload serving."""
import json
import pytest
import sqlite3

from pathlib import Path

from fastapi.testclient import TestClient

import main

from conftest import AUTH


# ── 6. Export / import ─────────────────────────────────────────────────────


def test_export_returns_all_entries(client, post):
    for i in range(3):
        post({"n": i})
    r = client.get("/logs/export", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert [it["payload"] for it in body["items"]] == [{"n": 2}, {"n": 1}, {"n": 0}]
    assert "export_date" in body


def test_export_q_filters_entries_and_total(client, post):
    post({"msg": "keep me"})
    post({"msg": "drop me"})
    r = client.get("/logs/export?q=KEEP", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert [it["payload"] for it in body["items"]] == [{"msg": "keep me"}]


def test_import_bare_list_restores_entries(client, post):
    for i in range(2):
        post({"n": i})
    exported = client.get("/logs/export", headers=AUTH).json()

    r = client.post("/logs/import", headers=AUTH, json=exported["items"])
    assert r.status_code == 200
    assert r.json()["imported"] == 2
    logs = client.get("/logs?limit=100", headers=AUTH).json()
    assert logs["total"] == 4
    assert [it["payload"] for it in logs["items"]] == [
        {"n": 0}, {"n": 1}, {"n": 1}, {"n": 0}
    ]


def test_export_import_roundtrip_from_exported_file(client, post):
    """The UI downloads /logs/export verbatim and uploads that same file."""
    post({"kind": "object", "nested": [1, 2]})
    post("a string")
    post(None)
    exported = client.get("/logs/export", headers=AUTH).json()

    r = client.post("/logs/import", headers=AUTH, json=exported)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 3

    restored = client.get("/logs?limit=100", headers=AUTH).json()
    assert restored["total"] == 6
    payloads = [it["payload"] for it in restored["items"]]
    # Every original value, including a null payload, must survive.
    assert payloads.count(None) == 2
    assert payloads.count("a string") == 2
    assert payloads.count({"kind": "object", "nested": [1, 2]}) == 2


def test_import_via_multipart_file(client, post):
    post({"n": 1})
    exported = client.get("/logs/export", headers=AUTH).json()
    file_bytes = json.dumps(exported).encode("utf-8")
    r = client.post(
        "/logs/import",
        headers=AUTH,
        files={"file": ("backup.json", file_bytes, "application/json")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    assert client.get("/logs", headers=AUTH).json()["total"] == 2


def test_import_rejects_malformed_input_cleanly(client):
    r = client.post(
        "/logs/import",
        headers={**AUTH, "Content-Type": "application/json"},
        content=b"{broken json",
    )
    assert r.status_code == 400

    r = client.post("/logs/import", headers=AUTH, json={"not": "an array"})
    assert r.status_code == 400

    assert client.get("/logs", headers=AUTH).json()["total"] == 0


def test_import_skips_malformed_entries_without_corruption(client):
    entries = [
        {"timestamp": "2026-01-01T00:00:00Z", "ip_address": "1.2.3.4", "payload": {"ok": 1}},
        {"timestamp": "2026-01-01T00:00:00Z", "ip_address": "1.2.3.4"},  # no payload
        "not an object",
    ]
    r = client.post("/logs/import", headers=AUTH, json=entries)
    assert r.status_code == 200
    assert r.json()["imported"] == 1
    logs = client.get("/logs", headers=AUTH).json()
    assert logs["total"] == 1
    assert logs["items"][0]["payload"] == {"ok": 1}


# ── 7. Multi-DB ────────────────────────────────────────────────────────────


def test_multidb_create_switch_isolation_and_pointer(client, post, env):
    r = client.post("/dbs", headers=AUTH, json={"name": "alpha"})
    assert r.status_code == 200, r.text
    assert r.json()["active"] == "alpha.db"
    post({"db": "alpha"})
    assert client.get("/logs", headers=AUTH).json()["total"] == 1

    r = client.post("/dbs", headers=AUTH, json={"name": "beta"})
    assert r.status_code == 200
    assert r.json()["active"] == "beta.db"
    # A newly created db is isolated from alpha's logs.
    assert client.get("/logs", headers=AUTH).json()["total"] == 0
    post({"db": "beta"})

    # The active pointer is persisted to disk.
    assert env.data_dir.joinpath(".active").read_text(encoding="utf-8").strip() == "beta.db"

    listing = client.get("/dbs", headers=AUTH).json()
    assert listing["active"] == "beta.db"
    names = {db["name"] for db in listing["dbs"]}
    assert {"alpha.db", "beta.db"} <= names

    # Switch back: alpha's row is still there and beta's is hidden.
    r = client.post("/dbs/activate", headers=AUTH, json={"name": "alpha"})
    assert r.status_code == 200
    assert r.json()["count"] == 1
    logs = client.get("/logs", headers=AUTH).json()
    assert logs["total"] == 1
    assert [it["payload"] for it in logs["items"]] == [{"db": "alpha"}]

    assert env.data_dir.joinpath(".active").read_text(encoding="utf-8").strip() == "alpha.db"


def test_multidb_rejects_invalid_names(client, post):
    for bad in ["../outside", "folder/db", "..", "evil\\db", ""]:
        r = client.post("/dbs", headers=AUTH, json={"name": bad})
        assert r.status_code == 400, (bad, r.text)
        r = client.post("/dbs/activate", headers=AUTH, json={"name": bad})
        assert r.status_code == 400, (bad, r.text)

    r = client.post("/dbs/activate", headers=AUTH, json={"name": "missing.db"})
    assert r.status_code == 404

    # None of the bad names changed the active db and its logs stay put.
    post({"still": "active"})
    assert client.get("/logs", headers=AUTH).json()["total"] == 1


def test_multidb_unnamed_create_uses_timestamped_name(client, post, env):
    r = client.post("/dbs", headers=AUTH, json={})
    assert r.status_code == 200, r.text
    name = r.json()["active"]
    assert name.startswith("logs-") and name.endswith(".db")
    assert (env.data_dir / name).is_file()
    assert env.data_dir.joinpath(".active").read_text().strip() == name


def test_multidb_startup_resumes_active_pointer(env, monkeypatch):
    # Simulate a restart: the pointer says beta.db; startup must honor it.
    env.data_dir.mkdir(parents=True, exist_ok=True)
    for name in ("logs.db", "beta.db"):
        conn = sqlite3.connect(env.data_dir / name)
        conn.execute(
            "CREATE TABLE logs (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "timestamp TEXT NOT NULL, ip_address TEXT NOT NULL, payload TEXT NOT NULL, "
            "filename TEXT, created_at TEXT)"
        )
        conn.commit()
        conn.close()
    env.data_dir.joinpath(".active").write_text("beta.db\n", encoding="utf-8")

    monkeypatch.setattr(main, "_active_db", main.DEFAULT_DB_NAME)
    with TestClient(main.app) as restarted:
        r = restarted.get("/dbs", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["active"] == "beta.db"


# ── 1b. GET /uploads/{filename} ────────────────────────────────────────────


def test_uploaded_file_is_served_at_frontend_link(client, post):
    entry = client.post(
        "/webhook",
        headers=AUTH,
        data={"note": "attached"},
        files={"file": ("note.txt", b"hello from upload", "text/plain")},
    )
    assert entry.status_code == 201
    filename = entry.json()["filename"]

    r = client.get(f"/uploads/{filename}")
    assert r.status_code == 200, r.text
    assert r.content == b"hello from upload"


def test_uploads_route_rejects_traversal_and_missing_files(client, env):
    for bad in ["../../etc/passwd", "..%2f..%2fetc%2fpasswd", "sub/file.txt"]:
        r = client.get(f"/uploads/{bad}")
        assert r.status_code in (400, 404), (bad, r.status_code)
    r = client.get("/uploads/no-such-file.txt")
    assert r.status_code == 404


# ── 8. SSE ─────────────────────────────────────────────────────────────────
#
# The portal TestClient transport cannot deliver SSE lines when the stream
# request shares its event loop with a second in-flight request (verified by
# probes in tests/probe_sse.py). So the live-delivery test spawns a real
# uvicorn server and streams with a plain httpx client — the closest
# production-equivalent check that is still fully deterministic and bounded.


def _run_uvicorn_probe():
    """Attach a real SSE stream, fire a webhook from a second client, and
    assert the live subscriber receives the pushed event.

    Spawns a throwaway uvicorn server on a free port: the Starlette TestClient
    portal transport cannot deliver SSE lines while a second request is in
    flight on the same event loop (verified in tests/probe_sse.py), so the
    only reliable live-delivery check is a real server.
    """
    import os
    import socket
    import subprocess
    import sys
    import time

    import httpx

    def _free_port() -> int:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    repo = Path(__file__).parent.parent
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", str(port)],
        cwd=repo,
        env={**os.environ, "API_KEY": "test-secret-key"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 15
        with httpx.Client(base_url=base, timeout=5.0) as http:
            up = False
            while time.time() < deadline:
                try:
                    if http.get("/logs", headers=AUTH).status_code == 200:
                        up = True
                        break
                except httpx.ConnectError:
                    time.sleep(0.3)
            if not up:
                raise AssertionError("uvicorn did not start in time")

            # Attach the SSE stream first, then fire the webhook from a second
            # client: a live subscriber must receive the pushed event.
            with http.stream("GET", "/stream", headers=AUTH, timeout=15.0) as stream:
                assert stream.status_code == 200
                with httpx.Client(base_url=base, timeout=5.0) as second:
                    r = second.post("/webhook", headers=AUTH, json={"sse": "hello"})
                    assert r.status_code == 201, r.text
                saw_log = False
                data_line = None
                for line in stream.iter_lines():
                    if not saw_log and line.startswith("event: log"):
                        saw_log = True
                        continue
                    if saw_log and line.startswith("data:"):
                        data_line = line
                        break
                assert saw_log, "SSE stream did not deliver the webhook's log event"
                assert data_line and "hello" in data_line
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_sse_delivers_log_event_after_webhook():
    _run_uvicorn_probe()


def test_sse_requires_auth(client):
    r = client.get("/stream")
    assert r.status_code == 403


# ── SSE backpressure ───────────────────────────────────────────────────────
#
# A wedged client (one that never reads) must not grow memory without bound:
# the broadcast path is allowed to drop it once its pending queue exceeds the
# cap, while healthy clients keep receiving events.


def test_sse_wedged_client_is_dropped_not_grown(client):
    import asyncio

    # Simulate a wedged SSE client: a queue that is only written, never read.
    wedged: asyncio.Queue = asyncio.Queue()
    main._clients.add(wedged)
    healthy: asyncio.Queue = asyncio.Queue()
    main._clients.add(healthy)
    try:
        loop = asyncio.new_event_loop()
        try:
            for i in range(1500):
                loop.run_until_complete(main.broadcast("log", {"i": i}))
        finally:
            loop.close()

        # The wedged queue must NOT hold 1500 events: it is either gone from
        # the client set or bounded at the documented cap.
        wedged_dropped = wedged not in main._clients
        wedged_bounded = wedged.qsize() <= 1000
        assert wedged_dropped or wedged_bounded, (
            f"wedged client kept {wedged.qsize()} pending events"
        )
        # The healthy client still has events queued.
        assert healthy.qsize() > 0
    finally:
        main._clients.discard(wedged)
        main._clients.discard(healthy)
