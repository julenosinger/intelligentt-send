"""Integration marker for GenLayer live tests.

Usage:
    pytest tests/ -m "not integration"  # skip live tests
    pytest tests/ -m integration        # run live GenLayer tests (needs GENLAYER_ACCOUNT_PK)
"""
import pytest


@pytest.mark.integration
def test_genlayer_live_marker():
    """Mark test as requiring GenLayer connection."""
    pass