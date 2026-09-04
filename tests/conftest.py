"""Pytest configuration and markers.

Usage:
    pytest tests/ -m "not integration"   # skip live network tests (default for CI)
    pytest tests/ -m integration         # run live GenLayer/network tests
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: test requires a live network connection (GenLayer/Arc RPC)"
    )
