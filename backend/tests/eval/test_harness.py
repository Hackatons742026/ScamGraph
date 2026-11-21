import pytest

from backend.eval.harness import PairLabel, build_report, loo_report, scenarios, synthetic_variants


def test_seven_synthetic_scenarios_are_deterministic():
    assert len(synthetic_variants()) == 7
    assert scenarios() == scenarios()
    assert all(row["passed"] for row in scenarios())
    assert {row["criterion"] for row in scenarios()} == {
        "known_campaign", "new_candidate", "needs_review"}


def test_loo_confusion_and_accuracy():
    report = loo_report([
        ("synthetic-1", "known_campaign", "known_campaign"),
        ("synthetic-2", "new_candidate", "needs_review"),
    ])
    assert report["accuracy"] == .5
    assert report["confusion"]["matrix"][1][2] == 1


def test_report_false_merges_and_ablation():
    labels = [PairLabel("a", "b", True, True), PairLabel("a", "c", False, False)]
    report = build_report(labels, {("a", "b"): (True, True), ("a", "c"): (True, False)},
        [("a", "known_campaign", "known_campaign")],
        {"all-signals": {("a", "b"): (True, True)}, "no-tier-a": {}})
    assert report["false_merges"] == 1
    assert [row["config"] for row in report["ablation"]] == ["all-signals", "no-tier-a"]


def test_loo_rejects_unknown_outcomes():
    with pytest.raises(ValueError, match="unknown routing outcome"):
        loo_report([("synthetic", "known_campaign", "unknown")])
