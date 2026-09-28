"""Scenario specification (docs/scenario-spec.md §2) — minimal generic form.

A scenario is explicit, versioned configuration of the environment; it contains no code
(Scenario ≠ Algorithm). Parameters are validated against the pack's parameter model when the spec
is registered (:mod:`industrial_ai.scenario.registry`); files are read by
:mod:`industrial_ai.scenario.loading`.
"""

from typing import Literal

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
    source: Literal["pack", "user"] = "pack"
    """``pack`` = shipped with the scenario pack; ``user`` = created through the API."""

    @field_validator("version")
    @classmethod
    def _semver(cls, value: str) -> str:
        parse_version(value)
        return value
