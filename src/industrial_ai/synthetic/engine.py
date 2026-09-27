"""Synthetic Data Engine: runs a registered generator and returns a validated, traceable dataset.

Steps (docs/synthetic-data-api.md §4): resolve generator → validate parameters → generate →
build dataset with provenance → validate schema and constraints → (optionally) register in the
catalog. Invalid output is never returned: it raises :class:`ConstraintViolationError` carrying
the validation report.
"""

import hashlib
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from industrial_ai.core.errors import ConstraintViolationError, GeneratorParameterError
from industrial_ai.foundation.catalog import DatasetCatalog
from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetBundle,
    DatasetSchema,
    SourceInfo,
    SourceType,
    build_dataset,
)
from industrial_ai.foundation.provenance import (
    ComponentRef,
    InputRef,
    Lineage,
    ScenarioRef,
    TransformationStep,
    ValidationRef,
)
from industrial_ai.foundation.validation import ConstraintSet, ValidationReport, validate_dataset
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.synthetic.base import (
    GenerationConfig,
    GenerationSize,
    SyntheticDataGenerator,
    SyntheticDataset,
)
from industrial_ai.synthetic.registry import GeneratorRegistry


class GenerationRequest(BaseModel):
    """One generation run. Serialisable, so it can come from the API or a config file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    generator_id: str
    generator_version: str | None = None
    """``None`` = latest registered version (the resolved version is recorded)."""
    dataset_id: str
    version: str = "1"
    name: str | None = None
    description: str = ""
    output_schema: DatasetSchema
    constraints: ConstraintSet = ConstraintSet()
    scenario: ScenarioSpec | None = None
    seed: int = Field(ge=0)
    size: GenerationSize = GenerationSize()
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    reference_dataset_id: str | None = None
    reference_version: str | None = None
    tags: tuple[str, ...] = ("synthetic",)


class SyntheticEngine:
    def __init__(self, registry: GeneratorRegistry, catalog: DatasetCatalog | None = None) -> None:
        self._registry = registry
        self._catalog = catalog

    def generate(
        self,
        request: GenerationRequest,
        reference: Dataset | DatasetBundle | None = None,
        *,
        register: bool = False,
        created_at: datetime | None = None,
    ) -> SyntheticDataset:
        """Run ``request``. ``reference`` may be passed directly or via ``reference_dataset_id``.

        Raises:
            PluginNotFoundError: unknown generator / version.
            GeneratorParameterError: invalid parameters or inputs.
            ConstraintViolationError: generated data fails validation.
        """
        generator = self._registry.get(request.generator_id, request.generator_version)
        params = _validated_parameters(generator, request.parameters)
        reference = self._resolve_reference(request, reference)
        output = generator.generate(
            request.output_schema,
            request.constraints,
            request.scenario,
            request.seed,
            request.size,
            params,
            reference,
        )
        warnings = [*output.warnings, *_unused_scenario_parameters(generator, request.scenario)]
        config = GenerationConfig(
            generator_id=generator.generator_id,
            generator_version=generator.generator_version,
            schema_id=request.output_schema.schema_id,
            schema_version=request.output_schema.schema_version,
            constraints=request.constraints,
            scenario=request.scenario,
            seed=request.seed,
            size=request.size,
            parameters=params.model_dump(mode="json"),
        )
        lineage = Lineage(
            inputs=_input_refs(reference),
            component=ComponentRef(id=generator.generator_id, version=generator.generator_version),
            parameters=config.parameters,
            scenario=_scenario_ref(request.scenario),
            seed=request.seed,
            transformations=(
                *output.transformations,
                *(
                    [TransformationStep(step="warnings", details={"messages": list(warnings)})]
                    if warnings
                    else []
                ),
            ),
        )
        source = SourceInfo(
            name=request.name or request.dataset_id,
            description=request.description,
            source_type=SourceType.SYNTHETIC,
            source=f"synthetic:{generator.generator_id}@{generator.generator_version}",
            tags=request.tags,
        )

        def build(validation: ValidationRef | None) -> Dataset:
            return build_dataset(
                dataset_id=request.dataset_id,
                version=request.version,
                schema=request.output_schema,
                data=output.data,
                source=source,
                lineage=lineage.model_copy(update={"validation": validation}),
                created_at=created_at,
            )

        report = validate_dataset(build(None), request.constraints, _references(reference))
        if not report.passed:
            raise ConstraintViolationError(
                f"{request.dataset_id}@{request.version}: generated data failed "
                f"{len(report.failures)} check(s): "
                + "; ".join(f"{f.check} {f.target} ({f.violations})" for f in report.failures[:5]),
                report,
            )
        dataset = build(ValidationRef(passed=True, report_id=_report_id(report)))
        result = SyntheticDataset(
            dataset_id=dataset.dataset_id,
            version=dataset.version,
            schema=dataset.schema,
            data=dataset.data,
            metadata=dataset.metadata,
            provenance=dataset.provenance,
            generation_config=config,
            validation_report=report,
            warnings=tuple(warnings),
        )
        if register:
            if self._catalog is None:
                raise GeneratorParameterError("register=True needs an engine with a catalog")
            self._catalog.register(result)
        return result

    def _resolve_reference(
        self, request: GenerationRequest, reference: Dataset | DatasetBundle | None
    ) -> Dataset | DatasetBundle | None:
        if request.reference_dataset_id is None:
            return reference
        if reference is not None:
            raise GeneratorParameterError("pass either reference or reference_dataset_id, not both")
        if self._catalog is None:
            raise GeneratorParameterError("reference_dataset_id needs an engine with a catalog")
        return self._catalog.get(request.reference_dataset_id, request.reference_version)


def _validated_parameters(
    generator: SyntheticDataGenerator, parameters: dict[str, JsonValue]
) -> BaseModel:
    try:
        return generator.parameter_model.model_validate(parameters)
    except ValidationError as exc:
        raise GeneratorParameterError(
            f"invalid parameters for {generator.generator_id}@{generator.generator_version}: {exc}"
        ) from exc


def _unused_scenario_parameters(
    generator: SyntheticDataGenerator, scenario: ScenarioSpec | None
) -> list[str]:
    if scenario is None:
        return []
    unused = sorted(set(scenario.parameters) - generator.scenario_parameters)
    if not unused:
        return []
    return [
        f"scenario {scenario.scenario_id!r} parameters not applied by "
        f"{generator.generator_id}: {unused}"
    ]


def _input_refs(reference: Dataset | DatasetBundle | None) -> tuple[InputRef, ...]:
    if reference is None:
        return ()
    if isinstance(reference, Dataset):
        return (reference.as_input(),)
    return tuple(reference.tables[name].as_input() for name in sorted(reference.tables))


def _references(reference: Dataset | DatasetBundle | None) -> dict[str, Dataset]:
    if isinstance(reference, DatasetBundle):
        return {t.schema.schema_id: t for t in reference.tables.values()}
    if isinstance(reference, Dataset):
        return {reference.schema.schema_id: reference}
    return {}


def _scenario_ref(scenario: ScenarioSpec | None) -> ScenarioRef | None:
    if scenario is None:
        return None
    return ScenarioRef(
        scenario_id=scenario.scenario_id, version=scenario.version, parameters=scenario.parameters
    )


def _report_id(report: ValidationReport) -> str:
    return "sha256:" + hashlib.sha256(report.model_dump_json().encode()).hexdigest()
