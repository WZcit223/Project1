"""Generic scenario registry and YAML loading (docs/scenario-spec.md §2)."""

from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from industrial_ai.core.errors import (
    DuplicatePluginError,
    PluginNotFoundError,
    ScenarioValidationError,
)
from industrial_ai.scenario import (
    ScenarioRegistry,
    ScenarioSpec,
    load_scenario,
    load_scenarios,
    register_directory,
)


class Params(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: float = Field(default=1.0, ge=0.0, le=5.0)
    window_days: int = Field(default=0, ge=0)


def spec(
    scenario_id: str = "high", version: str = "1.0.0", **parameters: JsonValue
) -> ScenarioSpec:
    return ScenarioSpec(
        scenario_id=scenario_id, version=version, pack="demo", title="t", parameters=parameters
    )


def write(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def test_register_get_latest_and_list() -> None:
    registry = ScenarioRegistry("demo", Params)
    registry.register(spec(level=1.3))
    registry.register(spec(version="1.1.0", level=1.4))
    registry.register(spec("base"))
    assert registry.get("high").version == "1.1.0"
    assert registry.get("high", "1.0.0").parameters == {"level": 1.3}
    assert registry.keys() == [("base", "1.0.0"), ("high", "1.0.0"), ("high", "1.1.0")]
    assert "base" in registry and len(registry) == 3
    with pytest.raises(PluginNotFoundError):
        registry.get("missing")
    with pytest.raises(DuplicatePluginError):
        registry.register(spec(level=2.0))


def test_effective_parameters_include_defaults() -> None:
    registry = ScenarioRegistry("demo", Params)
    effective = registry.validate_parameters(spec(level=1.3))
    assert effective == Params(level=1.3, window_days=0)


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        (spec(level=9.0), "invalid parameters"),  # out of range
        (spec(levle=1.3), "invalid parameters"),  # misspelt name
        (
            ScenarioSpec(scenario_id="x", version="1.0.0", pack="other", title="t"),
            "belongs to pack 'other'",
        ),
    ],
)
def test_invalid_scenarios_are_rejected_at_registration(bad: ScenarioSpec, match: str) -> None:
    registry = ScenarioRegistry("demo", Params)
    with pytest.raises(ScenarioValidationError, match=match):
        registry.register(bad)
    assert len(registry) == 0


def test_load_scenario_from_yaml(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "high.yaml",
        """
scenario_id: high
version: 1.0.0
pack: demo
title: High
description: Higher level.
parameters:
  level: 1.3
tags: [demand]
""",
    )
    loaded = load_scenario(path)
    assert loaded == ScenarioSpec(
        scenario_id="high",
        version="1.0.0",
        pack="demo",
        title="High",
        description="Higher level.",
        parameters={"level": 1.3},
        tags=("demand",),
    )


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("scenario_id: [unclosed", "not valid YAML"),
        ("- a\n- b\n", "expected a mapping"),
        ("scenario_id: x\nversion: 1.0\npack: demo\ntitle: t\n", "invalid scenario"),
        ("scenario_id: x\nversion: 1.0.0\npack: demo\ntitle: t\ncode: rm\n", "invalid scenario"),
        ("scenario_id: !!python/object:os.system {}\n", "not valid YAML"),  # safe_load only
    ],
)
def test_malformed_files_are_rejected(tmp_path: Path, text: str, match: str) -> None:
    with pytest.raises(ScenarioValidationError, match=match):
        load_scenario(write(tmp_path, "bad.yaml", text))


def test_load_directory_in_file_name_order(tmp_path: Path) -> None:
    for name in ("b.yaml", "a.yml"):
        write(tmp_path, name, f"scenario_id: {name[0]}\nversion: 1.0.0\npack: demo\ntitle: t\n")
    write(tmp_path, "notes.txt", "ignored")
    assert [s.scenario_id for s in load_scenarios(tmp_path)] == ["a", "b"]
    registry = ScenarioRegistry("demo", Params)
    assert len(register_directory(registry, tmp_path)) == 2
    with pytest.raises(ScenarioValidationError, match="does not exist"):
        load_scenarios(tmp_path / "missing")
