"""SSE delivery probes: pin down a mechanism that streams a live event.

All three use the Starlette TestClient portal transport (httpx ASGITransport
buffers the whole body and cannot drive infinite streams):
A: stream in a background thread, webhook from the main thread.
B: stream in the main thread, webhook from a background thread.
C: a real uvicorn server + httpx client (closest to production).
"""
import os
from pathlib import Path
os.environ.setdefault("API_KEY", "test-secret-key")

from types import SimpleNamespace

import pytest

import main

AUTH = {"Authorization": "Bearer test-secret-key"}

@pytest.fixture()
def env(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "ACTIVE_POINTER", data_dir / ".active")
    monkeypatch.setattr(main, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(main, "_active_db", main.DEFAULT_DB_NAME)
    return SimpleNamespace(data_dir=data_dir, upload_dir=upload_dir)


def test_probe_a_main_thread_posts(env):
    import contextlib
    import threading
    import time
    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        got = {}

        def stream_reader():
            # Plain portal streaming with no concurrent request: proves whether
            # the TestClient can deliver SSE lines at all.
            with contextlib.suppress(Exception) as cm:
                with client.stream("GET", "/stream", headers=AUTH) as stream:
                    print(f"[A] stream {stream.status_code}", flush=True)
                    for i, line in enumerate(stream.iter_lines()):
                        print(f"[A] line {i}: {line[:50]!r}", flush=True)
                        got.setdefault("lines", []).append(line)
                        if i >= 2:
                            return
            got["exc"] = cm.exception

        t = threading.Thread(target=stream_reader, daemon=True)
        t.start()
        time.sleep(8)
        t.join(timeout=5)
        print(f"[A] alive={t.is_alive()} exc={got.get('exc')!r} lines={got.get('lines')!r}", flush=True)
        assert len(got.get("lines", [])) >= 2, "A: no SSE lines delivered by portal transport"


def test_probe_b_background_thread_posts(env):
    import threading
    import time
    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        done = {}

        def worker():
            time.sleep(0.5)
            r = client.post("/webhook", headers=AUTH, json={"probe": "b"})
            done["webhook"] = r.status_code

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        saw_log = False
        with client.stream("GET", "/stream", headers=AUTH) as stream:
            print(f"[B] stream {stream.status_code}", flush=True)
            for i, line in enumerate(stream.iter_lines()):
                if line.startswith("event: log"):
                    saw_log = True
                    print("[B] log delivered", flush=True)
                    break
                if i > 40:
                    break
        t.join(timeout=5)
        print(f"[B] webhook {done.get('webhook')}", flush=True)
        assert saw_log, "B: SSE event not delivered"


def test_probe_c_real_server(env):
    import subprocess
    import sys
    import time

    import httpx

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", "8765"],
        cwd=Path(__file__).parent.parent,
        env={**os.environ, "API_KEY": "test-secret-key"},
    )
    try:
        base = "http://127.0.0.1:8765"
        deadline = time.time() + 10
        with httpx.Client(base_url=base, timeout=3.0) as http:
            while time.time() < deadline:
                try:
                    r = http.get("/logs", headers=AUTH)
                    if r.status_code == 200:
                        break
                except httpx.ConnectError:
                    time.sleep(0.3)
            else:
                raise AssertionError("uvicorn did not start")

            # Open the stream FIRST (the SSE client attaches to the event bus),
            # then fire the webhook from a second client: the live client must
            # receive the pushed event — the actual consumer behavior.
            with http.stream("GET", "/stream", headers=AUTH, timeout=10.0) as stream:
                with httpx.Client(base_url=base, timeout=5.0) as second:
                    r = second.post("/webhook", headers=AUTH, json={"probe": "c"})
                print(f"[C] webhook {r.status_code}", flush=True)
                saw_log = False
                for line in stream.iter_lines():
                    if line.startswith("event: log"):
                        saw_log = True
                        print("[C] log delivered", flush=True)
                        break
                    if "event: connected" in line:
                        print("[C] connected", flush=True)
                assert saw_log, "C: SSE event not delivered"
    finally:
        proc.terminate()
        proc.wait(timeout=10)
