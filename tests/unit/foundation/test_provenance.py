"""Tests for industrial_ai.foundation.provenance.record."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from industrial_ai.foundation.provenance import (
    ComponentRef,
    InputRef,
    OutputRef,
    ProvenanceRecord,
    ScenarioRef,
    TransformationStep,
)


def record() -> ProvenanceRecord:
    return ProvenanceRecord(
        artifact_id="syn_demand@1",
        artifact_type="dataset",
        created_at=datetime(2026, 9, 27, tzinfo=UTC),
        framework_version="0.1.0.dev0",
        inputs=(InputRef(dataset_id="m5_subset", version="1", content_hash="sha256:ab"),),
        component=ComponentRef(id="time_series", version="1.0.0"),
        parameters={"noise_scale": 1.0, "profile": [1, 2, 3]},
        scenario=ScenarioRef(
            scenario_id="high_demand", version="1.0.0", parameters={"demand_multiplier": 1.3}
        ),
        seed=20260927,
        transformations=(TransformationStep(step="calibrate", details={"method": "negbin"}),),
        output=OutputRef(content_hash="sha256:cd", row_count=10),
    )


def test_json_round_trip() -> None:
    original = record()
    assert ProvenanceRecord.model_validate_json(original.model_dump_json()) == original


def test_records_are_immutable() -> None:
    with pytest.raises(ValidationError):
        record().seed = 1


def test_unknown_fields_are_rejected() -> None:
    data = record().model_dump(mode="json") | {"unexpected": True}
    with pytest.raises(ValidationError):
        ProvenanceRecord.model_validate(data)
