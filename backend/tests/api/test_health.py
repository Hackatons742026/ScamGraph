from fastapi.testclient import TestClient

from backend.api import main

app = main.app


def test_health_and_unknown_api():
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok", "version": "1"}
    missing = client.get("/api/missing")
    assert missing.status_code == 404
    assert missing.json() == {"error": "not_found", "detail": "Not found"}


def test_health_initializes_and_checks_configured_sqlite_database(tmp_path, monkeypatch):
    database = tmp_path / "isolated" / "scamgraph.db"
    monkeypatch.setenv("SCAMGRAPH_DB", str(database))

    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1"}
    assert database.is_file()


def test_health_reports_safe_not_ready_error_for_unusable_database_path(tmp_path, monkeypatch):
    database_parent = tmp_path / "a-file"
    database_parent.write_text("synthetic", encoding="utf-8")
    monkeypatch.setenv("SCAMGRAPH_DB", str(database_parent / "scamgraph.db"))

    response = TestClient(app).get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"error": "http_error", "detail": "Database is not ready"}


def test_spa_serves_assets_and_fallback_without_path_escape(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("synthetic shell", encoding="utf-8")
    (dist / "app.js").write_text("synthetic asset", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("must-not-leak", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", dist)
    client = TestClient(app)

    assert client.get("/app.js").text == "synthetic asset"
    assert client.get("/incidents/example").text == "synthetic shell"
    escaped = client.get("/%2e%2e/secret.txt")
    assert "must-not-leak" not in escaped.text
