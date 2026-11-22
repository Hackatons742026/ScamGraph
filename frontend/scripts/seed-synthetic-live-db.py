"""Dev-only (#7): a synthetic live database so the frontend can run with VITE_USE_MOCKS=false without the dataset.

Saves 7 synthetic incidents with evidence, then runs the same analysis step as backend.api.live.execute_import
(backend.api.live.analysis_snapshot: link, cluster, decisions consistent with membership). Every value is synthetic (example-scam.test, fake hashes).

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
REPO_ROOT = Path(__file__).resolve().parents[2]
if Path(sys.argv[1]).exists():
    sys.exit(f"{sys.argv[1]} already exists; pass a new path")
if Path(sys.argv[1]).resolve().is_relative_to(REPO_ROOT):
    sys.exit("refusing to create a database inside the repository; pass a path outside it (e.g. /tmp/...)")
sys.path.insert(0, str(REPO_ROOT))
from backend.api.live import analysis_snapshot  # noqa: E402
from backend.db import Repository  # noqa: E402
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

# Analysis: the exact step execute_import runs after parsing.
edges, groups, decisions, clusters = analysis_snapshot(repo)
repo.save_analysis(edges, groups, decisions)
grouped = {row["id"]: None for row in repo.list_incidents()}
now = datetime.now(timezone.utc).isoformat()
# Run summary in the shape execute_import writes (live.run() reads `details` and `artifacts_by_kind`).
stats: dict[str, dict[str, int]] = {}
for identifier in grouped:
    for item in repo.get_artifacts(identifier):
        value = stats.setdefault(item["kind"], {"total": 0, "parsed": 0, "failed": 0, "partial": 0})
        value["total"] += 1
        value["failed" if item["parse_status"] == "failed" else "parsed"] += 1
        value["partial"] += item["parse_status"] == "partial"
repo.save_run("run-syn-1", "done", now, finished_at=now, summary={
    "incidents": len(grouped), "details": [{"incident_id": i, "artifacts": len(repo.get_artifacts(i))} for i in grouped],
    "duplicates": 0, "secrets_redacted": 0, "artifacts_by_kind": stats,
    "campaigns": len(clusters.campaigns), "networks": len(clusters.networks), "unassigned": len(clusters.unassigned),
    "new_candidates": sum(d["outcome"] == "new_candidate" for d in decisions),
    "needs_review": sum(d["outcome"] == "needs_review" for d in decisions)})
print("edges", [(e.source, e.target, e.level, e.tier) for e in edges])
print("campaigns", [(c.id, c.members) for c in clusters.campaigns], "networks", [(n.id, n.members) for n in clusters.networks])
