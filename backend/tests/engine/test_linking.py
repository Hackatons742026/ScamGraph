from math import isclose, log

from backend.engine.linking import candidate_pairs, link_incidents
from backend.pipeline.models import Evidence


def ev(kind, value, tier, family=None, **kwargs):
    return Evidence(
        type=kind,
        tier=tier,
        family=family,
        value_hash=value,
        display=kwargs.pop("display", f"masked-{value}"),
        artifact_id=kwargs.pop("artifact_id", f"artifact-{value}"),
        **kwargs,
    )


def corpus(left, right, extras=8):
    rows = {"left": left, "right": right}
    rows.update({f"other-{n}": [ev("unique", f"u-{n}", "C")] for n in range(extras)})
    return rows


def one_edge(rows):
    edges = link_incidents(rows)
    assert len(edges) == 1
    return edges[0]


def test_tier_a_links_alone_and_keeps_provenance():
    edge = one_edge(corpus(
        [ev("pixel_id", "px", "A", artifact_id="a", funnel_step=1)],
        [ev("pixel_id", "px", "A", artifact_id="b", funnel_step=2)],
    ))
    assert edge.level == "campaign"
    assert edge.low_confidence is True
    assert edge.evidence[0].artifact_ids == ("a", "b")
    assert edge.evidence[0].funnel_steps == (1, 2)


def test_repeated_observations_keep_all_provenance():
    left = [
        ev("pixel_id", "px", "A", artifact_id="a1", funnel_step=1),
        ev("pixel_id", "px", "A", artifact_id="a2", funnel_step=2),
    ]
    right = [
        ev("pixel_id", "px", "A", artifact_id="b1", funnel_step=3),
        ev("pixel_id", "px", "A", artifact_id="b2", funnel_step=4),
    ]
    match = one_edge(corpus(left, right)).evidence[0]
    assert match.artifact_ids == ("a1", "a2", "b1", "b2")
    assert match.funnel_steps == (1, 2, 3, 4)


def test_kit_counts_once_and_never_makes_campaign_by_itself():
    shared = [ev("dom", "dom", "B", "kit"), ev("api_path", "api", "B", "kit")]
    edge = one_edge(corpus(shared, shared))
    assert edge.level == "network"
    assert edge.families == ("kit",)


def test_two_b_families_make_campaign():
    shared = [ev("dom", "dom", "B", "kit"), ev("domain", "host", "B", "domain")]
    assert one_edge(corpus(shared, shared)).level == "campaign"


def test_creative_needs_three_images_or_one_near_identical_ad():
    two = [ev("image_phash", f"img-{n}", "B", "creative") for n in range(2)]
    assert link_incidents(corpus(two, two)) == []
    three = [*two, ev("image_phash", "img-3", "B", "creative")]
    assert one_edge(corpus(three, three)).level == "network"
    ad = [ev("ad_creative_phash", "ad", "B", "creative")]
    assert one_edge(corpus(ad, ad)).level == "network"


def test_c_only_adds_score_and_two_c_types_are_network_only():
    one = [ev("sentence", "text", "C")]
    assert link_incidents(corpus(one, one)) == []
    two = [*one, ev("brand", "brand", "C")]
    edge = one_edge(corpus(two, two))
    assert edge.level == "network"
    assert edge.tier == "C"


def test_ignored_and_high_df_values_do_not_link():
    ignored = [ev("server_ip", "cdn", "A", ignored=True, ignore_reason="cdn_ip")]
    assert link_incidents(corpus(ignored, ignored)) == []
    rows = {f"i-{n}": [ev("domain", "common", "B", "domain")] for n in range(4)}
    rows.update({f"i-{n}": [ev("unique", f"u-{n}", "C")] for n in range(4, 10)})
    assert link_incidents(rows) == []


def test_engine_rejects_public_libraries_placeholder_phones_and_small_docs():
    ignored_pairs = [
        [ev("script_hash", "lib", "A", display="jQuery public library")],
        [ev("phone", "phone", "A", display="000 000 000")],
        [ev("dom", "tiny", "B", "kit", ignored=True, ignore_reason="small_doc")],
    ]
    for shared in ignored_pairs:
        assert link_incidents(corpus(shared, shared)) == []


def test_weight_is_log_n_over_df_and_missing_is_not_dissimilar():
    left = [ev("pixel_id", "rare", "A"), ev("left_only", "l", "C")]
    right = [ev("pixel_id", "rare", "A"), ev("right_only", "r", "C")]
    edge = one_edge(corpus(left, right))
    assert edge.comparable == 1
    assert isclose(edge.evidence[0].weight, log(10 / 2))


def test_candidate_generation_uses_shared_values():
    rows = corpus([ev("pixel_id", "px", "A")], [ev("pixel_id", "px", "A")])
    assert ("left", "right") in candidate_pairs(rows)
