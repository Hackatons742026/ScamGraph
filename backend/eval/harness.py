"""Deterministic evaluation using synthetic cases and optional local pair labels."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from backend.engine.linking import LinkEdge
from backend.engine.memory import classify, cluster_incidents

PAIR_COLUMNS = ("left_id", "right_id", "campaign", "network")
OUTCOMES = ("known_campaign", "new_candidate", "needs_review")


@dataclass(frozen=True)
class PairLabel:
    left_id: str
    right_id: str
    campaign: bool
    network: bool
    mentor_campaign: bool | None = None
    mentor_network: bool | None = None


def _boolean(value: str, *, optional: bool = False) -> bool | None:
    value = value.strip().lower()
    if optional and not value:
        return None
    if value not in {"0", "1", "false", "true"}:
        raise ValueError(f"expected boolean 0/1/false/true, got {value!r}")
    return value in {"1", "true"}


def load_pairs(path: str | Path) -> list[PairLabel]:
    """Load labels from an explicitly supplied local CSV path."""
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(PAIR_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"missing pair columns: {', '.join(sorted(missing))}")
        rows = []
        for index, row in enumerate(reader, 2):
            left, right = row["left_id"].strip(), row["right_id"].strip()
            if not left or not right or left == right:
                raise ValueError(f"invalid incident pair on row {index}")
            rows.append(PairLabel(left, right, bool(_boolean(row["campaign"])),
                bool(_boolean(row["network"])), _boolean(row.get("mentor_campaign", ""), optional=True),
                _boolean(row.get("mentor_network", ""), optional=True)))
    return rows


def metric(expected: Iterable[bool], predicted: Iterable[bool]) -> dict[str, float | int]:
    pairs = list(zip(expected, predicted, strict=True))
    tp = sum(want and got for want, got in pairs)
    fp = sum(not want and got for want, got in pairs)
    fn = sum(want and not got for want, got in pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "tp": tp, "fp": fp, "fn": fn}


def confusion(expected: Sequence[str], predicted: Sequence[str]) -> dict[str, object]:
    if any(value not in OUTCOMES for value in (*expected, *predicted)):
        raise ValueError("unknown routing outcome")
    matrix = [[0 for _ in OUTCOMES] for _ in OUTCOMES]
    for want, got in zip(expected, predicted, strict=True):
        matrix[OUTCOMES.index(want)][OUTCOMES.index(got)] += 1
    return {"labels": list(OUTCOMES), "matrix": matrix}


def pair_report(labels: Sequence[PairLabel], predictions: Mapping[tuple[str, str], tuple[bool, bool]]) -> dict:
    predicted = [predictions.get(tuple(sorted((row.left_id, row.right_id))), (False, False)) for row in labels]
    mentor = [(row.campaign, row.mentor_campaign) for row in labels if row.mentor_campaign is not None]
    return {"n_pairs": len(labels), "mentor_verified": len(mentor),
        "agreement": sum(a == b for a, b in mentor) / len(mentor) if mentor else None,
        "campaign": metric((row.campaign for row in labels), (row[0] for row in predicted)),
        "network": metric((row.network for row in labels), (row[1] for row in predicted))}


def _edge(source: str, target: str, *, level: str = "campaign", tier: str = "A",
          comparable: int = 2) -> LinkEdge:
    return LinkEdge(source, target, level, tier, (), 1.0, comparable, False, ())


def synthetic_variants() -> list[tuple[str, str, bool, list[LinkEdge], str | None]]:
    """Seven synthetic cases; these are the only built-in tuning inputs."""
    return [
        ("Exact tier-A match", "known_campaign", True, [_edge("x", "a")], None),
        ("Multi-signal match", "known_campaign", True, [_edge("x", "a", tier="B")], None),
        ("Network-only link", "new_candidate", True, [_edge("x", "a", level="network")], None),
        ("No shared evidence", "new_candidate", True, [], None),
        ("Insufficient coverage", "needs_review", False, [], None),
        ("Conflicting campaigns", "needs_review", True, [_edge("x", "a"), _edge("x", "c")], None),
        ("Excluded incident", "new_candidate", True, [_edge("x", "a")], "a"),
    ]


def scenarios() -> list[dict]:
    base = [_edge("a", "b"), _edge("c", "d")]
    clusters = cluster_incidents(["a", "b", "c", "d"], base)
    output = []
    for number, (name, expected, coverage, edges, excluded) in enumerate(synthetic_variants(), 1):
        actual = classify("x", edges, clusters, coverage_ok=coverage, exclude_incident=excluded).outcome
        output.append({"id": number, "name": name, "criterion": expected,
            "passed": actual == expected, "details": f"expected {expected}; got {actual}"})
    return output


def loo_report(rows: Sequence[tuple[str, str, str]]) -> dict:
    expected, predicted = [row[1] for row in rows], [row[2] for row in rows]
    values = [{"incident_id": identifier, "expected": want, "predicted": got, "correct": want == got}
              for identifier, want, got in rows]
    return {"accuracy": sum(row["correct"] for row in values) / len(values) if values else 0.0,
        "rows": values, "confusion": confusion(expected, predicted)}


def build_report(labels: Sequence[PairLabel] = (),
                 predictions: Mapping[tuple[str, str], tuple[bool, bool]] | None = None,
                 loo_rows: Sequence[tuple[str, str, str]] = (),
                 ablations: Mapping[str, Mapping[tuple[str, str], tuple[bool, bool]]] | None = None) -> dict:
    pairs = pair_report(labels, predictions or {})
    loo = loo_report(loo_rows)
    variants = []
    for name, variant in sorted((ablations or {"all-signals": predictions or {}}).items()):
        scored = pair_report(labels, variant)["campaign"]
        variants.append({"config": name, "campaign_p": scored["precision"],
            "campaign_r": scored["recall"], "false_merges": scored["fp"],
            "loo_routing": loo["accuracy"]})
    return {"generated_at": None, "scenarios": scenarios(), "pairs": pairs,
        "false_merges": pairs["campaign"]["fp"], "loo": loo, "ablation": variants}
