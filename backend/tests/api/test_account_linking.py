"""Uploads linked by shared accounts (e-mail, bank account) and never by script file names."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.db import Repository
from backend.pipeline.models import Coverage, Incident

client = TestClient(app)


def _live(tmp_path, monkeypatch) -> Repository:
    monkeypatch.setenv("SCAMGRAPH_DB", str(tmp_path / "accounts.db"))
    monkeypatch.setenv("SCAMGRAPH_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SCAMGRAPH_SALT", "synthetic-accounts-salt")
    repo = Repository(tmp_path / "accounts.db")
    for index in range(6):  # background memory below the high-frequency cut-off
        repo.save_incident(Incident(f"synthetic-background-{index}", "synthetic", coverage=Coverage()))
    return repo


def _upload(name: str, body: str):
    page = (f"<html><head><title>{name}</title><script src='js/main.js'></script></head>"
            f"<body><h1>{name}</h1><p>{body}</p></body></html>").encode()
    return client.post("/api/classify", files={"files": (f"{name}.html", page, "text/html")})


def test_shared_email_account_groups_two_sites(tmp_path, monkeypatch) -> None:
    _live(tmp_path, monkeypatch)
    first = _upload("vista-one", "Wypłaty realizuje dział finansowy: wyplaty.vista@vista-mail.test")
    second = _upload("vista-two", "Pytania o bonus kieruj na adres WYPLATY.VISTA@vista-mail.test")
    assert first.json()["outcome"] == "new_candidate"
    assert second.json()["outcome"] == "known_campaign"
    displays = {e["display"] for e in second.json()["evidence"] if e["type"] == "email"}
    assert displays == {"wy…@vista-mail.test"}


def test_shared_spaced_bank_account_groups_two_sites(tmp_path, monkeypatch) -> None:
    _live(tmp_path, monkeypatch)
    _upload("paczka-one", "Dopłatę przelej na rachunek PL61 1090 1014 0000 0712 1981 2874.")
    second = _upload("paczka-two", "Opłata na konto 61 1090 1014 0000 0712 1981 2874 w ciągu doby.")
    assert second.json()["outcome"] == "known_campaign"
    assert not any(e["type"] == "phone" for e in second.json()["evidence"])
    assert "1090 1014" not in str(second.json())  # never the raw account, not even in sentences


def test_same_script_file_name_alone_does_not_link(tmp_path, monkeypatch) -> None:
    _live(tmp_path, monkeypatch)
    _upload("shop-one", "Wiosenna promocja w sklepie.")
    second = _upload("shop-two", "Letnia wyprzedaż w innym sklepie.")
    assert second.json()["outcome"] != "known_campaign"
    assert second.json()["candidate_edges"] == []
