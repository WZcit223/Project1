"""Optional check against the owner's real M5 subset in data/raw/m5_subset/ (never committed).

Run with ``uv run pytest -m m5_local``; skipped when the folder is absent (always the case in CI).
"""

from pathlib import Path

import pytest

from industrial_ai.foundation.validation import validate_bundle
from industrial_ai_warehouse.adapters.m5 import M5Adapter

SUBSET_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "m5_subset"

pytestmark = [
    pytest.mark.m5_local,
    pytest.mark.skipif(not SUBSET_DIR.is_dir(), reason="no local M5 subset in data/raw/m5_subset"),
]


def test_real_m5_subset_converts_and_validates() -> None:
    bundle = M5Adapter().load(SUBSET_DIR)
    report = validate_bundle(bundle)
    assert report.passed, report.failures
    assert not report.skipped


def test_real_m5_subset_hybrid_environment_is_valid() -> None:
    from industrial_ai_warehouse.generators import build_hybrid_bundle, generate_operations

    retail = M5Adapter().load(SUBSET_DIR)
    report = validate_bundle(build_hybrid_bundle(retail, generate_operations(retail, seed=1)))
    assert report.passed, report.failures
    assert not report.skipped
