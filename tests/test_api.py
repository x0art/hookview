"""Core API tests: webhook persistence, logs, delete, UI route.

Each test targets a concrete consumer-visible behavior; several encode the
current contract that the TDD workstream is driving to green.
"""
import json

import main
import pytest

from conftest import AUTH
import sqlite3



# ── 1. POST /webhook JSON types ───────────────────────────────────────────


@pytest.mark.parametrize(
    "payload",
    [
        {"event": "deploy", "status": "success"},
        "just a string",
        [1, 2, 3, "mixed"],
        42,
        3.5,
        True,
        False,
        None,
    ],
    ids=["object", "string", "array", "int", "float", "true", "false", "null"],
)
def test_webhook_persists_every_json_type_verbatim(client, post, payload):
    entry = post(payload)
    assert entry["payload"] == payload
    assert entry["filename"] is None

    # And the stored row round-trips through /logs too.
    logs = client.get("/logs", headers=AUTH)
    assert logs.status_code == 200
    stored = logs.json()
    assert stored["total"] == 1
    assert stored["items"][0]["payload"] == payload


def test_webhook_requires_bearer_auth(client):
    r = client.post("/webhook", json={"a": 1})
    assert r.status_code == 403

    r = client.post("/webhook", json={"a": 1}, headers={"Authorization": "Bearer wrong-key"})
    assert r.status_code == 403


def test_webhook_rejects_invalid_json(client):
    r = client.post(
        "/webhook",
        headers={**AUTH, "Content-Type": "application/json"},
        content=b"{not json",
    )
    assert r.status_code == 400


# ── 2. POST /webhook multipart ────────────────────────────────────────────


def test_webhook_multipart_stores_file_and_payload(client, post, env):
    entry = post(None, filename="report.txt")
    assert entry["filename"] is not None
    assert entry["filename"].endswith("report.txt")
    assert entry["payload"] == {"message": "deploy artifact"}

    # The file is inside the uploads dir and keeps its bytes.
    file_path = env.upload_dir / entry["filename"]
    assert file_path.is_file()
    assert file_path.read_bytes() == b"file-content"

    # The log row links the file.
    logs = client.get("/logs", headers=AUTH)
    assert logs.json()["items"][0]["filename"] == entry["filename"]


def test_webhook_multipart_path_traversal_filename_stays_in_uploads(client, post, env):
    entry = post(None, filename="../../evil.txt")
    # Saved name must be a bare filename: no path separators, no '..'.
    saved = entry["filename"]
    assert ".." not in saved
    assert "/" not in saved and "\\" not in saved
    # The content must live inside the uploads directory only.
    file_path = env.upload_dir / saved
    assert file_path.is_file()
    assert file_path.resolve().is_relative_to(env.upload_dir.resolve())


def test_webhook_multipart_without_file(client, post):
    r = client.post(
        "/webhook",
        headers=AUTH,
        data={"just": "fields"},
    )
    assert r.status_code == 201
    entry = r.json()
    assert entry["payload"] == {"just": "fields"}
    assert entry["filename"] is None


# ── 3. GET /logs ───────────────────────────────────────────────────────────


def test_logs_pagination_newest_first(client, post):
    for i in range(5):
        post({"seq": i})
    first = client.get("/logs?limit=2&offset=0", headers=AUTH).json()
    assert first["total"] == 5
    assert [it["id"] for it in first["items"]] == [5, 4]
    second = client.get("/logs?limit=2&offset=2", headers=AUTH).json()
    assert [it["id"] for it in second["items"]] == [3, 2]
    last = client.get("/logs?limit=2&offset=4", headers=AUTH).json()
    assert [it["id"] for it in last["items"]] == [1]
    assert last["total"] == 5


def test_logs_q_search_filters_items_and_total(client, post):
    post({"msg": "hello world"})
    post({"msg": "goodbye"})
    post({"msg": "HELLO again"})

    r = client.get("/logs?q=hello", headers=AUTH)
    body = r.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    payloads = {it["payload"]["msg"] for it in body["items"]}
    assert payloads == {"hello world", "HELLO again"}

    r = client.get("/logs?q=nosuchthing", headers=AUTH)
    assert r.json() == {"items": [], "total": 0}


def test_logs_after_id_pages_ascending(client, post):
    for i in range(4):
        post({"seq": i})
    r = client.get("/logs?limit=10&after_id=1", headers=AUTH)
    body = r.json()
    assert [it["id"] for it in body["items"]] == [2, 3, 4]


def test_logs_before_id_pages_descending(client, post):
    for i in range(4):
        post({"seq": i})
    r = client.get("/logs?limit=10&before_id=4", headers=AUTH)
    body = r.json()
    assert [it["id"] for it in body["items"]] == [3, 2, 1]


# ── 4. DELETE /logs/{id} ──────────────────────────────────────────────────


def test_delete_log_removes_row_and_decrements_total(client, post):
    entry = post({"bye": 1})
    log_id = entry["id"]
    assert client.get("/logs", headers=AUTH).json()["total"] == 1

    r = client.delete(f"/logs/{log_id}", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"deleted": True, "id": log_id}
    assert client.get("/logs", headers=AUTH).json()["total"] == 0

    # Deleting the same id again is a clean 404.
    r = client.delete(f"/logs/{log_id}", headers=AUTH)
    assert r.status_code == 404


def test_delete_log_removes_linked_upload_file(client, post, env):
    entry = post(None, filename="gone.txt")
    saved = entry["filename"]
    assert (env.upload_dir / saved).is_file()

    r = client.delete(f"/logs/{entry['id']}", headers=AUTH)
    assert r.status_code == 200
    assert not (env.upload_dir / saved).exists()


# ── 5. POST /logs/delete-bulk ─────────────────────────────────────────────


def test_bulk_delete_mixed_valid_and_invalid_ids(client, post):
    entries = [post({"n": i}) for i in range(3)]
    ids = [entries[0]["id"], entries[1]["id"], 999999]

    r = client.post("/logs/delete-bulk", headers=AUTH, json={"ids": ids})
    assert r.status_code == 200
    body = r.json()
    assert body["deleted"] == 2
    assert set(body["ids"]) == {entries[0]["id"], entries[1]["id"]}

    remaining = client.get("/logs?limit=100", headers=AUTH).json()
    assert remaining["total"] == 1
    assert remaining["items"][0]["id"] == entries[2]["id"]


def test_bulk_delete_duplicate_ids_delete_once(client, post):
    entry = post({"once": 1})
    r = client.post(
        "/logs/delete-bulk",
        headers=AUTH,
        json={"ids": [entry["id"], entry["id"]]},
    )
    assert r.json()["deleted"] == 1
    assert client.get("/logs", headers=AUTH).json()["total"] == 0


def test_bulk_delete_empty_ids_succeeds(client, post):
    post({"stay": 1})
    r = client.post("/logs/delete-bulk", headers=AUTH, json={"ids": []})
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": 0, "ids": []}
    assert client.get("/logs", headers=AUTH).json()["total"] == 1


# ── Import performance / limits ───────────────────────────────────────────


def test_import_large_batch_is_single_transaction(client, post):
    """A 1000-entry import lands intact in one response without per-row commits."""
    entries = [
        {"timestamp": f"2026-01-01T00:00:{i:02d}Z", "ip_address": "10.0.0.1", "payload": {"i": i}}
        for i in range(1000)
    ]
    r = client.post("/logs/import", headers=AUTH, json=entries)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1000
    logs = client.get("/logs?limit=1000", headers=AUTH).json()
    assert logs["total"] == 1000


def test_import_oversized_body_rejected(client):
    """An import body well over 10 MB is rejected with 413, not imported."""
    big = [
        {"timestamp": "2026-01-01T00:00:00Z", "ip_address": "10.0.0.1", "payload": "x" * 100_000}
        for _ in range(150)
    ]  # ~15 MB serialized
    r = client.post("/logs/import", headers=AUTH, json=big)
    assert r.status_code == 413, r.text
    assert client.get("/logs", headers=AUTH).json()["total"] == 0


# ── 9. Static UI route ────────────────────────────────────────────────────
def test_index_serves_html_with_expected_ids(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    for marker in ('id="apiKey"', 'id="connectBtn"', 'id="logBody"', 'id="logContainer"'):
        assert marker in r.text


# ── DB switch atomicity ───────────────────────────────────────────────────


def test_activate_is_atomic_with_in_flight_write(client, post, env):
    """A write must never straddle a database switch.

    While one request is mid-write on db A, activating db B from a second
    client must not make the in-flight write land in B. The switch holds the
    db lock, so the writer either completes on A or the activation waits —
    either way the row lands in exactly one database.
    """
    import concurrent.futures
    from fastapi.testclient import TestClient

    # Two entries on the default db so it is never empty during the race.
    post({"seed": 1})
    post({"seed": 2})

    def writer():
        """Run one webhook write on its own portal client."""
        with TestClient(main.app) as c:
            r = c.post("/webhook", headers=AUTH, json={"inflight": True})
            assert r.status_code == 201, r.text
            return r

    def activator():
        """Switch to a second database on its own portal client."""
        with TestClient(main.app) as c:
            r = c.post("/dbs", headers=AUTH, json={"name": "race-target"})
            assert r.status_code == 200, r.text
            return r

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        fw = pool.submit(writer)
        fa = pool.submit(activator)
        fw.result(timeout=20)
        ar = fa.result(timeout=20)

    # The activation switched the active database.
    assert ar.json()["active"] == "race-target.db"

    # Count rows in both databases directly.

    def count_rows(db_name):
        p = env.data_dir / db_name
        if not p.is_file():
            return 0
        conn = sqlite3.connect(p)
        try:
            n = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
        finally:
            conn.close()
        return n

    on_default = count_rows(main.DEFAULT_DB_NAME)
    on_target = count_rows("race-target.db")
    total_rows = on_default + on_target
    # 2 seeds + exactly 1 in-flight write, regardless of which db it landed in.
    assert total_rows == 3, (
        f"in-flight write did not land in exactly one db: "
        f"default={on_default} target={on_target}"
    )
    # The in-flight payload must be present in exactly one of the two dbs.
    import json as _json

    def has_inflight(db_name):
        p = env.data_dir / db_name
        if not p.is_file():
            return False
        conn = sqlite3.connect(p)
        try:
            rows = conn.execute("SELECT payload FROM logs").fetchall()
        finally:
            conn.close()
        return any(_json.loads(r[0]) == {"inflight": True} for r in rows)

    # The in-flight write must be in exactly one database, not both.
    assert sum((
        has_inflight(main.DEFAULT_DB_NAME),
        has_inflight("race-target.db"),
    )) == 1, "in-flight write duplicated across both databases"
