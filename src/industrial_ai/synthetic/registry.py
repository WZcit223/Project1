"""Generator registry (docs/synthetic-data-api.md §4)."""

from industrial_ai.core.registry import Registry
from industrial_ai.synthetic.base import GeneratorInfo, SyntheticDataGenerator

GeneratorRegistry = Registry[SyntheticDataGenerator]


def new_generator_registry() -> GeneratorRegistry:
    """An empty registry keyed by ``(generator_id, generator_version)``."""
    return Registry("generator", key=lambda g: (g.generator_id, g.generator_version))


def describe(generator: SyntheticDataGenerator) -> GeneratorInfo:
    return GeneratorInfo(
        generator_id=generator.generator_id,
        generator_version=generator.generator_version,
        description=generator.description,
        parameter_schema=generator.parameter_model.model_json_schema(),
        scenario_parameters=tuple(sorted(generator.scenario_parameters)),
    )
