from backend.engine.linking import LinkEdge, MatchedEvidence
from backend.engine.memory import classify, cluster_incidents


def edge(a, b, level="campaign", tier="B", score=1.0, comparable=2, family="kit"):
    evidence = MatchedEvidence("dom", tier, family, "masked", "hash", score, (), (), "synthetic")
    return LinkEdge(a, b, level, tier, (family,) if family else (), score,
                    comparable, comparable < 2, (evidence,))


def test_network_campaign_and_explicit_unassigned():
    edges = [edge("a", "b"), edge("b", "c", "network"), edge("d", "e", "network")]
    result = cluster_incidents("abcdef", edges)
    assert [campaign.members for campaign in result.campaigns] == [("a", "b")]
    assert {network.members for network in result.networks} == {("a", "b", "c"), ("d", "e")}
    assert result.unassigned == ("c", "d", "e", "f")
    assert result.campaigns[0].evidence_types == ("dom",)


def test_large_component_is_split_by_louvain():
    left, right = ("a", "b", "c"), ("d", "e", "f")
    edges = [edge(a, b, score=5) for group in (left, right) for index, a in enumerate(group)
             for b in group[index + 1:]]
    edges.append(edge("c", "d", score=0.01))
    result = cluster_incidents((*left, *right), edges, max_campaign_size=3)
    assert {campaign.members for campaign in result.campaigns} == {left, right}
    reversed_result = cluster_incidents(reversed((*left, *right)), list(reversed(edges)),
                                        max_campaign_size=3)
    assert reversed_result.campaigns == result.campaigns


def test_memory_known_new_review_conflict_and_exclusion():
    base = cluster_incidents("abcd", [edge("a", "b"), edge("c", "d")])
    known = classify("new", [edge("new", "a", tier="A", comparable=1)], base, coverage_ok=False)
    assert known.outcome == "known_campaign"
    assert known.campaign_id == "campaign-a"

    new = classify("new", [edge("new", "a", "network", comparable=3)], base, coverage_ok=True)
    assert new.outcome == "new_candidate"
    review = classify("new", [], base, coverage_ok=False)
    assert review.outcome == "needs_review"

    conflict = classify("new", [edge("new", "a"), edge("new", "c")], base, coverage_ok=True)
    assert conflict.outcome == "needs_review"
    assert "conflicts" in conflict.reasons[0]

    excluded = cluster_incidents("abc", [edge("a", "b")], exclude_incident="a")
    assert "a" not in excluded.unassigned
    assert excluded.campaigns == ()


def test_non_a_campaign_edge_needs_two_comparable_types():
    base = cluster_incidents("ab", [edge("a", "b")])
    result = classify("new", [edge("new", "a", comparable=1)], base, coverage_ok=True)
    assert result.outcome == "needs_review"


def test_classify_ignores_edges_not_incident_to_candidate():
    base = cluster_incidents("ab", [edge("a", "b")])
    result = classify("new", [edge("a", "b", tier="A")], base, coverage_ok=True)
    assert result.outcome != "known_campaign"


def test_classify_ignores_excluded_reference_match():
    base = cluster_incidents("ab", [edge("a", "b")])
    result = classify(
        "new", [edge("new", "a", tier="A")], base,
        coverage_ok=True, exclude_incident="a",
    )
    assert result.outcome == "needs_review"
