"""Application service: the single entry point the HTTP API uses (docs/application-api.md §5).

It wires settings, the dataset catalog, the run store, discovered scenario packs, user-defined
scenarios and the synthetic engine, and exposes orchestration-only operations. No algorithm or data
manipulation beyond reading stored results lives here.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Session, SQLModel, col, select

from industrial_ai.application.models import RunRecord, RunRequest
from industrial_ai.application.pack import ComponentInfo, PackRegistry, ScenarioPack, discover_packs
from industrial_ai.application.runner import WorkflowRunner
from industrial_ai.application.store import RunStore
from industrial_ai.application.views import (
    ComparisonRow,
    DatasetDetail,
    PackInfo,
    ReferenceInfo,
    RunCreate,
    RunResults,
    RunSummary,
    ScenarioDetail,
    TimePoint,
    TimeSeries,
)
from industrial_ai.core.config import Settings
from industrial_ai.core.errors import ApplicationError, RunRequestError
from industrial_ai.foundation.catalog import (
    DatasetCatalog,
    DatasetPreview,
    DatasetSummary,
    create_database_engine,
)
from industrial_ai.foundation.datasets import SourceType
from industrial_ai.scenario import ScenarioRegistry, ScenarioSpec
from industrial_ai.synthetic import (
    GenerationRequest,
    GeneratorInfo,
    GeneratorRegistry,
    SyntheticEngine,
    describe,
)
from industrial_ai.synthetic.generators import builtin_registry


class UserScenarioRow(SQLModel, table=True):
    __tablename__ = "application_user_scenario"
    __table_args__ = (UniqueConstraint("pack", "scenario_id", "version"),)

    id: int | None = Field(default=None, primary_key=True)
    pack: str = Field(index=True)
    scenario_id: str
    version: str
    created_at: datetime
    spec_json: str


class ApplicationService:
    def __init__(
        self,
        settings: Settings,
        packs: PackRegistry | None = None,
        generators: GeneratorRegistry | None = None,
    ) -> None:
        self._settings = settings
        self._catalog = DatasetCatalog.from_settings(settings)
        self._store = RunStore(settings.database_url, self._catalog)
        self._engine = create_database_engine(settings.database_url)
        SQLModel.metadata.create_all(self._engine, tables=[UserScenarioRow.__table__])  # type: ignore[attr-defined]
        self._packs = packs if packs is not None else discover_packs()
        self._generators = generators if generators is not None else builtin_registry()
        self._runner = WorkflowRunner(self._packs, self._store, scenarios=self.scenarios)

    # --- packs and references -----------------------------------------------------------------

    def list_packs(self) -> list[PackInfo]:
        return [
            PackInfo(
                pack_id=p.pack_id,
                pack_version=p.pack_version,
                title=p.title,
                description=p.description,
                requires_reference=p.requires_reference,
                scenario_ids=tuple(sorted({s.scenario_id for s in self.scenarios(p).list()})),
            )
            for p in self._packs.list()
        ]

    def list_references(self) -> list[ReferenceInfo]:
        return [
            ReferenceInfo(reference_id=ref, available=path.is_dir())
            for ref, path in sorted(self._settings.reference_dirs.items())
        ]

    def pack(self, pack_id: str) -> ScenarioPack:
        return self._packs.get(pack_id)

    def components(self, pack_id: str, kind: str | None = None) -> list[ComponentInfo]:
        return [c for c in self.pack(pack_id).components() if kind is None or c.kind == kind]

    # --- datasets -----------------------------------------------------------------------------

    def list_datasets(self, source_type: SourceType | None = None) -> list[DatasetSummary]:
        return self._catalog.list(source_type)

    def dataset(self, dataset_id: str, version: str | None = None) -> DatasetDetail:
        dataset = self._catalog.get(dataset_id, version)
        return DatasetDetail(
            summary=self._catalog.summary(dataset.dataset_id, dataset.version),
            table_schema=dataset.schema,
            metadata=dataset.metadata,
            provenance=dataset.provenance,
        )

    def preview(self, dataset_id: str, version: str | None, limit: int) -> DatasetPreview:
        return self._catalog.preview(dataset_id, version, limit)

    # --- synthetic data -----------------------------------------------------------------------

    def list_generators(self) -> list[GeneratorInfo]:
        return [describe(g) for g in self._generators.list()]

    def generate(self, request: GenerationRequest) -> DatasetSummary:
        """Run a generation request and register the result in the catalog."""
        engine = SyntheticEngine(self._generators, self._catalog)
        dataset = engine.generate(request, register=True)
        return self._catalog.summary(dataset.dataset_id, dataset.version)

    # --- scenarios ----------------------------------------------------------------------------

    def scenarios(self, pack: ScenarioPack) -> ScenarioRegistry:
        """The pack's scenarios plus the user-defined scenarios stored for it."""
        registry = pack.scenarios()
        for spec in self._user_scenarios(pack.pack_id):
            registry.register(spec)
        return registry

    def list_scenarios(self, pack_id: str) -> list[ScenarioSpec]:
        return self.scenarios(self.pack(pack_id)).list()

    def scenario(self, pack_id: str, scenario_id: str, version: str | None) -> ScenarioDetail:
        registry = self.scenarios(self.pack(pack_id))
        spec = registry.get(scenario_id, version)
        return ScenarioDetail(
            spec=spec,
            effective_parameters=registry.validate_parameters(spec).model_dump(mode="json"),
            parameter_schema=registry.parameter_model.model_json_schema(),
        )

    def create_scenario(self, spec: ScenarioSpec) -> ScenarioSpec:
        """Validate and store a user-defined scenario (immutable; a change needs a new version).

        Raises:
            PluginNotFoundError: unknown pack.
            ScenarioValidationError: wrong pack or invalid parameters.
            DuplicatePluginError: ``(scenario_id, version)`` already exists for the pack.
        """
        user_spec = spec.model_copy(update={"source": "user"})
        self.scenarios(self.pack(spec.pack)).register(user_spec)  # validates, detects duplicates
        with self._session() as session:
            session.add(
                UserScenarioRow(
                    pack=spec.pack,
                    scenario_id=spec.scenario_id,
                    version=spec.version,
                    created_at=datetime.now(UTC),
                    spec_json=user_spec.model_dump_json(),
                )
            )
            session.commit()
        return user_spec

    # --- runs ---------------------------------------------------------------------------------

    def start_run(self, body: RunCreate) -> RunRecord:
        """Resolve the reference id and execute the run synchronously (v0.1)."""
        reference = None
        if body.reference_id is not None:
            path = self._settings.reference_dirs.get(body.reference_id)
            if path is None:
                known = sorted(self._settings.reference_dirs)
                raise RunRequestError(f"unknown reference_id {body.reference_id!r}; known: {known}")
            reference = str(path)
        request = RunRequest(
            pack=body.pack,
            scenario_id=body.scenario_id,
            scenario_version=body.scenario_version,
            scenario_overrides=body.scenario_overrides,
            seed=body.seed,
            horizon_days=body.horizon_days,
            reference_id=body.reference_id,
            reference=reference,
            options=body.options,
        )
        return self._runner.run(request)

    def list_runs(self) -> list[RunSummary]:
        return [
            RunSummary(
                run_id=r.run_id,
                status=r.status,
                pack=r.pack,
                scenario_id=r.scenario.scenario_id,
                scenario_version=r.scenario.version,
                seed=r.request.seed,
                created_at=r.created_at.isoformat(),
                error=r.error,
            )
            for r in self._store.list()
        ]

    def run(self, run_id: str) -> RunRecord:
        return self._store.get(run_id)

    def results(self, run_id: str) -> RunResults:
        record = self._store.get(run_id)
        metric_ids = next(iter(record.variant_metrics.values()), {})
        return RunResults(
            run_id=record.run_id,
            status=record.status,
            scenario=record.scenario,
            labels=record.labels,
            variants=record.variant_metrics,
            supporting=record.supporting_metrics,
            metric_ids=tuple(metric_ids),
        )

    def timeseries(
        self,
        run_id: str,
        variant: str,
        table: str,
        column: str,
        filters: dict[str, str],
    ) -> TimeSeries:
        """Daily series of ``column`` from a stored result table, summed over matching entities."""
        record = self._store.get(run_id)
        key = f"{variant}.{table}"
        link = record.outputs.get(key)
        if link is None:
            raise ApplicationError(
                f"run {run_id} has no output {key!r}; available: {sorted(record.outputs)}"
            )
        dataset = self._catalog.get(link.dataset_id, link.version)
        time_column = dataset.schema.time_index
        if time_column is None or column not in dataset.data.columns:
            raise ApplicationError(f"{key} has no time index or no column {column!r}")
        frame = dataset.data
        for name, value in filters.items():
            if name not in dataset.schema.entity_keys:
                raise ApplicationError(f"{name!r} is not an entity key of {key}")
            frame = frame[frame[name].astype(str) == value]
        series = frame.groupby(time_column)[column].sum().sort_index()
        return TimeSeries(
            run_id=run_id,
            variant=variant,
            table=table,
            column=column,
            filter=filters,
            aggregation="sum",
            points=tuple(
                TimePoint(date=d.date(), value=float(v))
                for d, v in zip(pd.to_datetime(series.index), series.to_numpy(), strict=True)
            ),
        )

    def compare(self, run_ids: list[str]) -> list[ComparisonRow]:
        rows = []
        for run_id in run_ids:
            record = self._store.get(run_id)
            for variant, metrics in record.variant_metrics.items():
                rows.append(
                    ComparisonRow(
                        run_id=run_id,
                        scenario_id=record.scenario.scenario_id,
                        scenario_version=record.scenario.version,
                        variant=variant,
                        metrics=metrics,
                    )
                )
        return rows

    # --- internals ----------------------------------------------------------------------------

    def _user_scenarios(self, pack_id: str) -> list[ScenarioSpec]:
        with self._session() as session:
            rows = session.exec(
                select(UserScenarioRow)
                .where(UserScenarioRow.pack == pack_id)
                .order_by(col(UserScenarioRow.id))
            ).all()
        return [ScenarioSpec.model_validate_json(row.spec_json) for row in rows]

    @contextmanager
    def _session(self) -> Iterator[Session]:
        with Session(self._engine) as session:
            yield session
