"""Dev-only (#7): a synthetic live database so the frontend can run with VITE_USE_MOCKS=false without the dataset.

Saves 7 synthetic incidents with evidence, then runs the real engine (link, cluster, leave-one-out classify) exactly
like backend.api.live.execute_import's analysis step. Every value is synthetic (example-scam.test, fake hashes).

Usage (from the repo root, with backend requirements installed):
    SCAMGRAPH_SALT=synthetic-dev-salt python frontend/scripts/seed-synthetic-live-db.py /tmp/scamgraph-synthetic.db
    SCAMGRAPH_DB=/tmp/scamgraph-synthetic.db uvicorn backend.api.main:app --port 8000
Keep the database outside the repository (*.db is git-ignored and blocked by CI).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

if len(sys.argv) != 2:
    sys.exit("usage: seed-synthetic-live-db.py <path/to/new.db>")
if Path(sys.argv[1]).exists():
    sys.exit(f"{sys.argv[1]} already exists; pass a new path")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.api.live import stable_campaign  # noqa: E402
from backend.db import Repository  # noqa: E402
from backend.engine.linking import link_incidents  # noqa: E402
from backend.engine.memory import classify, cluster_incidents  # noqa: E402
from backend.pipeline.models import Artifact, Coverage, Evidence, Incident  # noqa: E402

repo = Repository(sys.argv[1])
A, B, C = "A", "B", "C"


def ev(t, tier, fam, h, disp, art, step=None, w=1.0):
    return Evidence(t, tier, fam, h, disp, w, art, step)


# Pairwise-shared values only (a value in > 30% of incidents is ignored as too common).
plan = {
    "inc-syn-a1": (["har", "html"], [("pixel_id", A, None, "h-pixel-1", "pixel_****91"), ("phone", C, None, "h-ph-a1", "+00 *** *** 101")]),
    "inc-syn-a2": (["har", "html", "image"], [("pixel_id", A, None, "h-pixel-1", "pixel_****91"), ("kit_hash", B, "kit", "h-kit-1", "kit:****ab"),
                                              ("click_domain", B, "tds", "h-tds-1", "click.example-scam.test")]),
    "inc-syn-b1": (["har", "html"], [("landing_domain", B, "domain", "h-dom-1", "offer.example-scam.test"), ("click_domain", B, "tds", "h-tds-2", "go.example-scam.test"),
                                     ("kit_hash", B, "kit", "h-kit-1", "kit:****ab")]),
    "inc-syn-b2": (["har", "image"], [("landing_domain", B, "domain", "h-dom-1", "offer.example-scam.test"), ("click_domain", B, "tds", "h-tds-2", "go.example-scam.test")]),
    "inc-syn-g": (["html", "image"], [("click_domain", B, "tds", "h-tds-1", "click.example-scam.test")]),
    "inc-syn-u": (["video"], [("ocr_phrase", C, None, "h-ocr-u", "synthetic headline")]),
    "inc-syn-v": (["adlib_json"], []),
}
for i, (iid, (kinds, items)) in enumerate(plan.items()):
    day = datetime(2026, 11, 1 + i, 10, tzinfo=timezone.utc)
    repo.save_incident(Incident(iid, f"synthetic/{iid}", title=f"Synthetic {iid}", first_seen=day, last_seen=day,
                                coverage=Coverage(kinds_present=kinds)))
    art = f"art-{iid}"
    repo.save_artifacts([Artifact(art, iid, kinds[0], f"synthetic/{iid}/a.{kinds[0]}", parse_status="ok")])
    repo.save_evidence(iid, [ev(t, tier, fam, h, d, art, 1) for t, tier, fam, h, d in items])

grouped = {row["id"]: [] for row in repo.list_incidents()}
for row in repo.list_evidence():
    grouped[row["incident_id"]].append(Evidence(row["type"], row["tier"], row["family"], row["value_hash"], row["display_value"],
                                                row["weight"], row["artifact_id"], row["funnel_step"], bool(row["ignored"]), row["ignore_reason"]))
edges = link_incidents(grouped)
clusters = cluster_incidents(grouped, edges)
now = datetime.now(timezone.utc).isoformat()
decisions = []
for identifier in grouped:
    memory = cluster_incidents(grouped, edges, exclude_incident=identifier)
    result = classify(identifier, [e for e in edges if identifier in {e.source, e.target}], memory,
                      coverage_ok=bool(grouped[identifier]), exclude_incident=identifier)
    decisions.append({"incident_id": identifier, "outcome": result.outcome, "campaign_id": stable_campaign(result, clusters, identifier),
                      "reasons": list(result.reasons), "decided_at": now})
repo.save_analysis(edges, [*clusters.networks, *clusters.campaigns], decisions)
repo.save_run("run-syn-1", "done", now, finished_at=now, summary={
    "incidents": len(grouped), "artifacts": len(grouped), "unique_artifacts": len(grouped), "duplicates": 0,
    "artifacts_by_kind": {}, "campaigns": len(clusters.campaigns), "networks": len(clusters.networks),
    "unassigned": len(clusters.unassigned), "needs_review": sum(d["outcome"] == "needs_review" for d in decisions),
    "new_candidates": sum(d["outcome"] == "new_candidate" for d in decisions), "secrets_redacted": 0})
print("edges", [(e.source, e.target, e.level, e.tier) for e in edges])
print("campaigns", [(c.id, c.members) for c in clusters.campaigns], "networks", [(n.id, n.members) for n in clusters.networks])
