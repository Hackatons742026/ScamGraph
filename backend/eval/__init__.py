"""Offline evaluation helpers; local labels are never bundled with the app."""

from .harness import build_report, load_pairs

__all__ = ["build_report", "load_pairs"]
