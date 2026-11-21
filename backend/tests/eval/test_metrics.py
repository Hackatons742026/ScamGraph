import csv

import pytest

from backend.eval.harness import PairLabel, confusion, load_pairs, metric, pair_report


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


@pytest.mark.parametrize("row,error", [
    ("a,a,1,1\n", "invalid incident pair"),
    ("a,b,maybe,1\n", "expected boolean"),
    (",b,0,0\n", "invalid incident pair"),
])
def test_pair_csv_rejects_invalid_rows(tmp_path, row, error):
    path = tmp_path / "pairs.csv"
    path.write_text("left_id,right_id,campaign,network\n" + row)
    with pytest.raises(ValueError, match=error):
        load_pairs(path)


def test_pair_keys_are_canonical_and_metrics_count_fp_fn():
    labels = [PairLabel("b", "a", True, True), PairLabel("a", "c", False, True)]
    report = pair_report(labels, {("a", "b"): (False, True), ("a", "c"): (True, False)})
    assert report["campaign"] == {"precision": 0, "recall": 0, "f1": 0, "tp": 0, "fp": 1, "fn": 1}
    assert report["network"] == {"precision": 1, "recall": .5, "f1": 2 / 3, "tp": 1, "fp": 0, "fn": 1}


def test_network_only_mentor_label_counts_as_verified():
    labels = [PairLabel("a", "b", False, True, mentor_network=True)]
    report = pair_report(labels, {})
    assert report["mentor_verified"] == 1 and report["agreement"] == 1
