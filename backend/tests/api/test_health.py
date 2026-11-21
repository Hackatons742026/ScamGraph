from fastapi.testclient import TestClient

from backend.api import main

app = main.app


def test_health_and_unknown_api():
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok", "version": "1"}
    assert client.get("/api/missing").status_code == 404


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
