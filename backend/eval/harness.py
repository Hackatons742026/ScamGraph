"""Deterministic evaluation using synthetic cases and optional local pair labels."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

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


def build_report(*args, **kwargs) -> dict:
    """Implemented below with the deterministic scenario runner."""
    raise NotImplementedError
