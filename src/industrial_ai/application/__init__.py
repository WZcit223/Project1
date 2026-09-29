"""Application layer: scenario packs, workflow orchestration, run store, application service.

The HTTP API depends on this package only (docs/architecture.md §2): the read models it needs from
lower layers are re-exported here.
"""

from industrial_ai.application.models import (
    DatasetLink,
    ResolvedRun,
    RunRecord,
    RunRequest,
    RunStatus,
)
from industrial_ai.application.pack import (
    ENTRY_POINT_GROUP,
    ComponentInfo,
    PackRegistry,
    PackRunOutput,
    ScenarioPack,
    discover_packs,
    new_pack_registry,
)
from industrial_ai.application.runner import WorkflowRunner, new_run_id
from industrial_ai.application.service import ApplicationService
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
from industrial_ai.foundation.catalog import DatasetPreview, DatasetSummary
from industrial_ai.foundation.datasets import SourceType
from industrial_ai.scenario import ScenarioSpec
from industrial_ai.synthetic import GenerationRequest, GeneratorInfo

__all__ = [
    "ApplicationService",
    "ComparisonRow",
    "DatasetDetail",
    "DatasetPreview",
    "DatasetSummary",
    "GenerationRequest",
    "GeneratorInfo",
    "PackInfo",
    "ReferenceInfo",
    "RunCreate",
    "RunResults",
    "RunSummary",
    "ScenarioDetail",
    "ScenarioSpec",
    "SourceType",
    "TimePoint",
    "TimeSeries",
    "ComponentInfo",
    "ENTRY_POINT_GROUP",
    "DatasetLink",
    "PackRegistry",
    "PackRunOutput",
    "ResolvedRun",
    "RunRecord",
    "RunRequest",
    "RunStatus",
    "RunStore",
    "ScenarioPack",
    "WorkflowRunner",
    "discover_packs",
    "new_pack_registry",
    "new_run_id",
]
