"""Tests for the synthetic generator protocol, registry and engine (TASK-SYN-001/002)."""

from pathlib import Path

import pytest

from industrial_ai.core.errors import (
    ConstraintViolationError,
    DuplicatePluginError,
    GeneratorParameterError,
    PluginNotFoundError,
)
from industrial_ai.foundation.catalog import DatasetCatalog
from industrial_ai.foundation.datasets import SourceType
from industrial_ai.foundation.validation import ConstraintSet, RangeConstraint
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.synthetic import (
    GenerationRequest,
    GenerationSize,
    SyntheticDataGenerator,
    SyntheticEngine,
    describe,
    new_generator_registry,
)

from .dummy import SCHEMA, DummyGenerator

SCENARIO = ScenarioSpec(
    scenario_id="double",
    version="1.0.0",
    pack="test",
    title="Double",
    parameters={"scale_multiplier": 2.0, "lead_time_delta": 3},
)


def engine(catalog: DatasetCatalog | None = None) -> SyntheticEngine:
    registry = new_generator_registry()
    registry.register(DummyGenerator())
    return SyntheticEngine(registry, catalog)


def request(**overrides: object) -> GenerationRequest:
    base: dict[str, object] = {
        "generator_id": "dummy",
        "dataset_id": "values",
        "output_schema": SCHEMA,
        "seed": 42,
        "size": GenerationSize(rows=20),
        "parameters": {"scale": 5.0},
    }
    return GenerationRequest.model_validate(base | overrides)


def test_dummy_satisfies_protocol_and_is_described() -> None:
    generator = DummyGenerator()
    assert isinstance(generator, SyntheticDataGenerator)
    info = describe(generator)
    assert info.generator_id == "dummy"
    assert "scale" in info.parameter_schema["properties"]
    assert info.scenario_parameters == ("scale_multiplier",)


def test_registry_rejects_duplicates() -> None:
    registry = new_generator_registry()
    registry.register(DummyGenerator())
    with pytest.raises(DuplicatePluginError):
        registry.register(DummyGenerator())


def test_generate_builds_traceable_synthetic_dataset() -> None:
    result = engine().generate(request(scenario=SCENARIO))
    assert result.metadata.source_type is SourceType.SYNTHETIC
    assert result.metadata.row_count == 20
    assert (result.generator_id, result.generator_version, result.random_seed) == (
        "dummy",
        "1.0.0",
        42,
    )
    prov = result.provenance
    assert prov.component is not None and prov.component.id == "dummy"
    assert prov.seed == 42 and prov.parameters == {"scale": 5.0, "negative": False}
    assert prov.scenario is not None and prov.scenario.scenario_id == "double"
    assert prov.validation is not None and prov.validation.passed
    assert result.validation_report.passed
    assert prov.transformations[0].step == "sample_uniform"
    assert result.data["value"].max() <= 10.0  # scale 5 x scenario multiplier 2


def test_unused_scenario_parameters_are_reported() -> None:
    result = engine().generate(request(scenario=SCENARIO))
    assert any("lead_time_delta" in w for w in result.warnings)
    assert result.provenance.transformations[-1].step == "warnings"


def test_same_inputs_and_seed_reproduce_the_same_data() -> None:
    first = engine().generate(request())
    second = engine().generate(request())
    other_seed = engine().generate(request(seed=43))
    assert first.metadata.content_hash == second.metadata.content_hash
    assert first.metadata.content_hash != other_seed.metadata.content_hash


def test_invalid_parameters_raise() -> None:
    with pytest.raises(GeneratorParameterError, match="invalid parameters"):
        engine().generate(request(parameters={"scale": "big"}))


def test_unknown_generator_raises() -> None:
    with pytest.raises(PluginNotFoundError):
        engine().generate(request(generator_id="nope"))


def test_constraint_violations_raise_with_report() -> None:
    with pytest.raises(ConstraintViolationError) as info:
        engine().generate(request(parameters={"negative": True}))
    assert "range" in str(info.value)
    constrained = request(
        constraints=ConstraintSet(constraints=(RangeConstraint(field="value", max=1),))
    )
    with pytest.raises(ConstraintViolationError):
        engine().generate(constrained)


def test_register_and_reference_via_catalog(tmp_path: Path) -> None:
    catalog = DatasetCatalog(f"sqlite:///{tmp_path / 'c.sqlite'}", tmp_path / "artifacts")
    first = engine(catalog).generate(request(), register=True)
    assert catalog.get("values").metadata.content_hash == first.metadata.content_hash
    second = engine(catalog).generate(
        request(dataset_id="values_2", reference_dataset_id="values"), register=True
    )
    assert second.provenance.inputs[0].content_hash == first.metadata.content_hash
    with pytest.raises(GeneratorParameterError, match="catalog"):
        engine().generate(request(), register=True)
