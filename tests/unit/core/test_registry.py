"""Tests for industrial_ai.core.registry."""

from dataclasses import dataclass

import pytest

from industrial_ai.core.errors import (
    DuplicatePluginError,
    IndustrialAIError,
    InvalidVersionError,
    PluginNotFoundError,
)
from industrial_ai.core.registry import Registry


@dataclass(frozen=True)
class DummyPlugin:
    plugin_id: str
    plugin_version: str


def make_registry() -> Registry[DummyPlugin]:
    return Registry("dummy plugin", key=lambda p: (p.plugin_id, p.plugin_version))


def test_register_and_get_exact_version() -> None:
    registry = make_registry()
    plugin = DummyPlugin("rule_based", "1.0.0")
    registry.register(plugin)
    assert registry.get("rule_based", "1.0.0") is plugin


def test_get_without_version_returns_highest_semver() -> None:
    registry = make_registry()
    for version in ["1.2.0", "1.10.0", "1.9.3"]:
        registry.register(DummyPlugin("time_series", version))
    assert registry.get("time_series").plugin_version == "1.10.0"


def test_duplicate_registration_is_rejected() -> None:
    registry = make_registry()
    registry.register(DummyPlugin("statistical", "1.0.0"))
    with pytest.raises(DuplicatePluginError, match="statistical"):
        registry.register(DummyPlugin("statistical", "1.0.0"))


def test_invalid_plugin_version_is_rejected() -> None:
    with pytest.raises(InvalidVersionError):
        make_registry().register(DummyPlugin("x", "latest"))


def test_unknown_id_and_version_raise_not_found() -> None:
    registry = make_registry()
    registry.register(DummyPlugin("a", "1.0.0"))
    with pytest.raises(PluginNotFoundError, match="'missing'"):
        registry.get("missing")
    with pytest.raises(PluginNotFoundError, match=r"available: 1\.0\.0"):
        registry.get("a", "2.0.0")


def test_list_keys_len_iter_are_ordered() -> None:
    registry = make_registry()
    for plugin_id, version in [("b", "1.0.0"), ("a", "2.0.0"), ("a", "1.0.0")]:
        registry.register(DummyPlugin(plugin_id, version))
    expected = [("a", "1.0.0"), ("a", "2.0.0"), ("b", "1.0.0")]
    assert registry.keys() == expected
    assert [(p.plugin_id, p.plugin_version) for p in registry.list()] == expected
    assert [(p.plugin_id, p.plugin_version) for p in registry] == expected
    assert len(registry) == 3


def test_contains_by_id_or_key() -> None:
    registry = make_registry()
    registry.register(DummyPlugin("a", "1.0.0"))
    assert "a" in registry
    assert ("a", "1.0.0") in registry
    assert ("a", "2.0.0") not in registry
    assert ("a", "bad") not in registry
    assert "b" not in registry
    assert 42 not in registry


def test_registries_are_independent() -> None:
    first, second = make_registry(), make_registry()
    first.register(DummyPlugin("a", "1.0.0"))
    assert "a" not in second


def test_registry_errors_share_framework_base_class() -> None:
    with pytest.raises(IndustrialAIError):
        make_registry().get("anything")
