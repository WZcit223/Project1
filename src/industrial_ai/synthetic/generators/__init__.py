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

__all__ = [
    "RuleBasedGenerator",
    "RuleBasedParameters",
    "StatisticalGenerator",
    "SeriesProfile",
    "StatisticalParameters",
    "TimeSeriesGenerator",
    "TimeSeriesParameters",
]
