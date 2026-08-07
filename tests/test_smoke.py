"""Smoke test for scholar-paper-cli package."""

import scholar_paper_cli


def test_version() -> None:
    """Package exposes expected version string."""
    assert scholar_paper_cli.__version__ == "0.1.0"
