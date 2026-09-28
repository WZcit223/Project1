"""Packs, references, datasets, generators, scenarios, models and strategies (TASK-API-001)."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from industrial_ai.api.deps import Service
from industrial_ai.application import (
    ComponentInfo,
    DatasetDetail,
    DatasetPreview,
    DatasetSummary,
    GenerationRequest,
    GeneratorInfo,
    PackInfo,
    ReferenceInfo,
    ScenarioDetail,
    ScenarioSpec,
    SourceType,
)

router = APIRouter(prefix="/api")
Pack = Annotated[str, Query(description="Scenario pack id, e.g. warehouse")]


@router.get("/scenario-packs", response_model=list[PackInfo], tags=["packs"])
def list_packs(service: Service) -> list[PackInfo]:
    """Installed scenario packs."""
    return service.list_packs()


@router.get("/references", response_model=list[ReferenceInfo], tags=["packs"])
def list_references(service: Service) -> list[ReferenceInfo]:
    """Configured reference data ids usable as ``reference_id`` in run requests."""
    return service.list_references()


@router.get("/datasets", response_model=list[DatasetSummary], tags=["datasets"])
def list_datasets(service: Service, source_type: SourceType | None = None) -> list[DatasetSummary]:
    return service.list_datasets(source_type)


@router.get("/datasets/{dataset_id}", response_model=DatasetDetail, tags=["datasets"])
def get_dataset(service: Service, dataset_id: str, version: str | None = None) -> DatasetDetail:
    """Metadata, schema and provenance of a dataset."""
    return service.dataset(dataset_id, version)


@router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreview, tags=["datasets"])
def preview_dataset(
    service: Service,
    dataset_id: str,
    version: str | None = None,
    limit: Annotated[int, Query(ge=0, le=1000)] = 50,
) -> DatasetPreview:
    return service.preview(dataset_id, version, limit)


@router.get("/synthetic/generators", response_model=list[GeneratorInfo], tags=["synthetic"])
def list_generators(service: Service) -> list[GeneratorInfo]:
    return service.list_generators()


@router.post(
    "/synthetic/generate",
    response_model=DatasetSummary,
    status_code=status.HTTP_201_CREATED,
    tags=["synthetic"],
)
def generate(service: Service, request: GenerationRequest) -> DatasetSummary:
    """Run a generation request; the result is registered in the catalog with provenance."""
    return service.generate(request)


@router.get("/scenarios", response_model=list[ScenarioSpec], tags=["scenarios"])
def list_scenarios(service: Service, pack: Pack) -> list[ScenarioSpec]:
    return service.list_scenarios(pack)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDetail, tags=["scenarios"])
def get_scenario(
    service: Service, scenario_id: str, pack: Pack, version: str | None = None
) -> ScenarioDetail:
    """Scenario spec, effective parameters and the pack's parameter schema."""
    return service.scenario(pack, scenario_id, version)


@router.post(
    "/scenarios",
    response_model=ScenarioSpec,
    status_code=status.HTTP_201_CREATED,
    tags=["scenarios"],
)
def create_scenario(service: Service, spec: ScenarioSpec) -> ScenarioSpec:
    """Create a user-defined scenario, validated against the pack's parameter model."""
    return service.create_scenario(spec)


@router.get("/models", response_model=list[ComponentInfo], tags=["components"])
def list_models(service: Service, pack: Pack, kind: str | None = None) -> list[ComponentInfo]:
    """Simulation plugins of a pack (kinds ``forecast``, ``simulation``)."""
    return [c for c in service.components(pack, kind) if c.kind != "strategy"]


@router.get("/strategies", response_model=list[ComponentInfo], tags=["components"])
def list_strategies(service: Service, pack: Pack) -> list[ComponentInfo]:
    return service.components(pack, "strategy")
