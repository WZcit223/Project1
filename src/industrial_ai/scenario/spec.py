"""Scenario specification (docs/scenario-spec.md §2) — minimal generic form.

A scenario is explicit, versioned configuration of the environment; it contains no code
(Scenario ≠ Algorithm). Parameter *validation* against a pack's parameter model, the scenario
registry and YAML loading arrive with the scenario engine (Phase 10).
"""

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from industrial_ai.core.versioning import parse_version


class ScenarioSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str
    pack: str
    title: str
    description: str = ""
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    tags: tuple[str, ...] = ()

    @field_validator("version")
    @classmethod
    def _semver(cls, value: str) -> str:
        parse_version(value)
        return value
