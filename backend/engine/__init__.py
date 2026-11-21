"""Explainable incident-linking engine."""

from .linking import LinkEdge, MatchedEvidence, link_incidents
from .memory import Campaign, Classification, ClusterResult, classify, cluster_incidents

__all__ = [
    "Campaign", "Classification", "ClusterResult", "LinkEdge", "MatchedEvidence",
    "classify", "cluster_incidents", "link_incidents",
]
