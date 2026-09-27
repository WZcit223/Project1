"""Smoke test: the framework package is importable and versioned."""

import industrial_ai


def test_package_exposes_version() -> None:
    assert industrial_ai.__version__.startswith("0.1.0")
