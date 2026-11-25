import os

os.environ.setdefault("API_KEY", "test-secret-key")

import pytest
from types import SimpleNamespace
from pathlib import Path
from fastapi.testclient import TestClient

import main

TEST_KEY = "test-secret-key"
AUTH = {"Authorization": f"Bearer {TEST_KEY}"}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolated data/upload dirs and a fresh active db for every test."""
    data_dir = tmp_path / "data"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "ACTIVE_POINTER", data_dir / ".active")
    monkeypatch.setattr(main, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(main, "_active_db", main.DEFAULT_DB_NAME)

    env = SimpleNamespace(data_dir=data_dir, upload_dir=upload_dir)

    return env



@pytest.fixture()
def client(env):
    """TestClient that runs the app lifespan (creates data/ + uploads/)."""
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def post(client):
    """Helper: POST a JSON webhook and return the stored entry."""

    def post(payload, filename=None):
        if filename is not None:
            files = {"file": (filename, b"file-content", "application/octet-stream")}
            data = {"message": "deploy artifact"}
            r = client.post("/webhook", headers=AUTH, data=data, files=files)
        else:
            r = client.post("/webhook", headers=AUTH, json=payload)
        assert r.status_code == 201, r.text
        return r.json()

    return post
