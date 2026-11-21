import csv

import pytest

from backend.eval.harness import confusion, load_pairs, metric, pair_report


def test_pair_csv_and_mentor_agreement(tmp_path):
    path = tmp_path / "pairs.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["left_id", "right_id", "campaign", "network", "mentor_campaign"])
        writer.writerow(["i1", "i2", "1", "true", "1"])
        writer.writerow(["i1", "i3", "0", "1", "1"])
    rows = load_pairs(path)
    report = pair_report(rows, {("i1", "i2"): (True, True)})
    assert report["campaign"] == {"precision": 1, "recall": 1, "f1": 1, "tp": 1, "fp": 0, "fn": 0}
    assert report["mentor_verified"] == 2 and report["agreement"] == .5


def test_csv_validation_and_metric_edges(tmp_path):
    path = tmp_path / "pairs.csv"
    path.write_text("left_id,right_id,campaign\na,b,maybe\n")
    with pytest.raises(ValueError, match="missing pair columns"):
        load_pairs(path)
    assert metric([], []) == {"precision": 0, "recall": 0, "f1": 0, "tp": 0, "fp": 0, "fn": 0}
    with pytest.raises(ValueError, match="unknown"):
        confusion(["invalid"], ["new_candidate"])


def test_confusion_orientation():
    result = confusion(["known_campaign", "new_candidate"], ["needs_review", "new_candidate"])
    assert result["matrix"][0][2] == 1 and result["matrix"][1][1] == 1
