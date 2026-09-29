"""Synthetic Data Engine: generator protocol, registry, engine and built-in generators."""

from industrial_ai.synthetic.base import (
    GeneratedData,
    GenerationConfig,
    GenerationSize,
    GeneratorInfo,
    SyntheticDataGenerator,
    SyntheticDataset,
)
from industrial_ai.synthetic.engine import GenerationRequest, SyntheticEngine
from industrial_ai.synthetic.registry import GeneratorRegistry, describe, new_generator_registry

__all__ = [
    "GeneratedData",
    "GenerationConfig",
    "GenerationRequest",
    "GenerationSize",
    "GeneratorInfo",
    "GeneratorRegistry",
    "SyntheticDataGenerator",
    "SyntheticDataset",
    "SyntheticEngine",
    "describe",
    "new_generator_registry",
]
