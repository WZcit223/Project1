"""Built-in generators (exactly three in v0.1: rule_based, statistical, time_series)."""

from industrial_ai.synthetic.generators.rule_based import RuleBasedGenerator, RuleBasedParameters
from industrial_ai.synthetic.generators.statistical import (
    StatisticalGenerator,
    StatisticalParameters,
)
from industrial_ai.synthetic.generators.time_series import (
    SeriesProfile,
    TimeSeriesGenerator,
    TimeSeriesParameters,
)
from industrial_ai.synthetic.registry import GeneratorRegistry, new_generator_registry


def builtin_registry() -> GeneratorRegistry:
    """A new registry containing the three built-in generators."""
    registry = new_generator_registry()
    for generator in (RuleBasedGenerator(), StatisticalGenerator(), TimeSeriesGenerator()):
        registry.register(generator)
    return registry


__all__ = [
    "RuleBasedGenerator",
    "RuleBasedParameters",
    "StatisticalGenerator",
    "SeriesProfile",
    "StatisticalParameters",
    "TimeSeriesGenerator",
    "TimeSeriesParameters",
    "builtin_registry",
]
