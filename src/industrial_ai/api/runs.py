"""Runs, results, time series and cross-run comparison (TASK-API-002)."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from industrial_ai.api.deps import Service
from industrial_ai.application import (
    ComparisonRow,
    RunCreate,
    RunRecord,
    RunResults,
    RunSummary,
    TimeSeries,
)
from industrial_ai.core.errors import ApplicationError

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("", response_model=RunRecord, status_code=status.HTTP_201_CREATED)
def create_run(service: Service, body: RunCreate) -> RunRecord:
    """Execute an end-to-end scenario run (synchronous in v0.1)."""
    return service.start_run(body)


@router.get("", response_model=list[RunSummary])
def list_runs(service: Service) -> list[RunSummary]:
    """All runs, most recent first."""
    return service.list_runs()


@router.get("/compare", response_model=list[ComparisonRow])
def compare_runs(
    service: Service, run_ids: Annotated[str, Query(description="Comma-separated run ids")]
) -> list[ComparisonRow]:
    """KPIs of several runs (e.g. one per scenario), one row per run and variant."""
    ids = [r.strip() for r in run_ids.split(",") if r.strip()]
    if not ids:
        raise ApplicationError("run_ids must name at least one run")
    return service.compare(ids)


@router.get("/{run_id}", response_model=RunRecord)
def get_run(service: Service, run_id: str) -> RunRecord:
    """Status, request, effective scenario, metrics and dataset links (provenance)."""
    return service.run(run_id)


@router.get("/{run_id}/results", response_model=RunResults)
def get_results(service: Service, run_id: str) -> RunResults:
    return service.results(run_id)


@router.get("/{run_id}/timeseries", response_model=TimeSeries)
def get_timeseries(
    service: Service,
    run_id: str,
    variant: str,
    table: str,
    column: str,
    filter: Annotated[
        list[str] | None, Query(description="Entity filters as key:value, repeatable")
    ] = None,
) -> TimeSeries:
    """Daily series of a result column, summed over the entities matching ``filter``."""
    filters: dict[str, str] = {}
    for item in filter or []:
        key, sep, value = item.partition(":")
        if not sep or not key:
            raise ApplicationError(f"filter {item!r} must be key:value")
        filters[key] = value
    return service.timeseries(run_id, variant, table, column, filters)
