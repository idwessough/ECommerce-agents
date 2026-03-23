"""Basic repository smoke tests."""

from pathlib import Path


def test_readme_exists() -> None:
    """Ensure the top-level README remains present."""
    assert Path("README.md").exists()
