"""Smoke tests: the framework and the warehouse scenario pack are importable and versioned."""

import importlib

import pytest

import industrial_ai
import industrial_ai_warehouse

FRAMEWORK_LAYERS = [
    "core",
    "foundation",
    "scenario",
    "synthetic",
    "simulation",
    "application",
    "api",
]


def test_framework_exposes_version() -> None:
    assert industrial_ai.__version__.startswith("0.1.0")


def test_warehouse_pack_exposes_version() -> None:
    assert industrial_ai_warehouse.__version__.startswith("0.1.0")


@pytest.mark.parametrize("layer", FRAMEWORK_LAYERS)
def test_framework_layer_is_importable(layer: str) -> None:
    module = importlib.import_module(f"industrial_ai.{layer}")
    assert module.__doc__, f"industrial_ai.{layer} must document its responsibility"
