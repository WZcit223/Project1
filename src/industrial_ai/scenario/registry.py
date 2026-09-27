"""Scenario registry per scenario pack (docs/scenario-spec.md §2).

A pack declares one Pydantic **parameter model** (names, types, defaults, valid ranges; unknown
names forbidden). Every scenario registered for the pack is validated against it, so an invalid or
misspelt parameter fails at registration, not silently at run time. Scenarios are discovered by
``scenario_id`` + ``version`` like plugins; the registry holds configuration only, never algorithms.
"""

import builtins

from pydantic import BaseModel, ValidationError

from industrial_ai.core.errors import ScenarioValidationError
from industrial_ai.core.registry import PluginKey, Registry
from industrial_ai.scenario.spec import ScenarioSpec


class ScenarioRegistry:
    """Validated scenarios of one pack, keyed by ``(scenario_id, version)``."""

    def __init__(self, pack: str, parameter_model: type[BaseModel]) -> None:
        self._pack = pack
        self._parameter_model = parameter_model
        self._specs: Registry[ScenarioSpec] = Registry(
            f"{pack} scenario", key=lambda s: (s.scenario_id, s.version)
        )

    @property
    def pack(self) -> str:
        return self._pack

    @property
    def parameter_model(self) -> type[BaseModel]:
        return self._parameter_model

    def register(self, spec: ScenarioSpec) -> None:
        """Validate ``spec`` against the pack and its parameter model, then register it.

        Raises:
            ScenarioValidationError: wrong pack, or parameters rejected by the parameter model.
            DuplicatePluginError: the same ``(scenario_id, version)`` is already registered.
        """
        if spec.pack != self._pack:
            raise ScenarioValidationError(
                f"scenario {spec.scenario_id!r} belongs to pack {spec.pack!r}, not {self._pack!r}"
            )
        self.validate_parameters(spec)
        self._specs.register(spec)

    def validate_parameters(self, spec: ScenarioSpec) -> BaseModel:
        """Effective parameters of ``spec``: its values plus the model's defaults."""
        try:
            return self._parameter_model.model_validate(spec.parameters)
        except ValidationError as exc:
            raise ScenarioValidationError(
                f"invalid parameters in scenario {spec.scenario_id!r} {spec.version}: {exc}"
            ) from exc

    def get(self, scenario_id: str, version: str | None = None) -> ScenarioSpec:
        """The scenario with ``scenario_id``: the given ``version``, or the latest if omitted."""
        return self._specs.get(scenario_id, version)

    def list(self) -> builtins.list[ScenarioSpec]:
        return self._specs.list()

    def keys(self) -> builtins.list[PluginKey]:
        return self._specs.keys()

    def __contains__(self, item: object) -> bool:
        return item in self._specs

    def __len__(self) -> int:
        return len(self._specs)
