"""Tests for industrial_ai.foundation.validation (one passing and one failing case per check)."""

from collections.abc import Callable

import pandas as pd
import pytest
from pydantic import TypeAdapter

from industrial_ai.foundation.datasets import (
    DatasetBundle,
    DatasetSchema,
    DType,
    FieldSpec,
    build_dataset,
)
from industrial_ai.foundation.provenance import Lineage
from industrial_ai.foundation.validation import (
    CheckStatus,
    Constraint,
    ConstraintSet,
    ForeignKeyConstraint,
    IntegerConstraint,
    NotNullConstraint,
    RangeConstraint,
    RelationConstraint,
    UniqueConstraint,
    ValidationReport,
    validate_bundle,
    validate_dataset,
)

from .builders import SOURCE, make_products, make_sales, sales_frame


def result_for(report: ValidationReport, check: str, field: str) -> tuple[CheckStatus, int]:
    matches = [r for r in report.results if r.check == check and r.target.endswith(field)]
    assert len(matches) == 1, f"expected one {check} result for {field}, got {matches}"
    return matches[0].status, matches[0].violations


def test_valid_dataset_passes_all_schema_checks() -> None:
    report = validate_dataset(make_sales(), references={"test.product": make_products()})
    assert report.passed, report.failures
    assert not report.skipped
    assert report.subject == "sales@1"


@pytest.mark.parametrize(
    ("mutate", "check", "field", "violations"),
    [
        (lambda df: df.assign(quantity=df["quantity"].astype("float64")), "dtype", "quantity", 4),
        (lambda df: df.assign(product_id=["A", "B", 3, "B"]), "dtype", "product_id", 1),
        (lambda df: df.assign(date=df["date"] + pd.Timedelta(hours=6)), "dtype", "date", 4),
        (lambda df: df.assign(product_id=["A", None, "A", "B"]), "not_null", "product_id", 1),
        (lambda df: df.assign(quantity=[3, -1, -2, 1]), "range", "quantity", 2),
        (lambda df: df.assign(unit_price=[0.0, 2.5, None, 2.5]), "range", "unit_price", 1),
        (
            lambda df: df.assign(channel=pd.Categorical(["store", "phone", "store", "store"])),
            "allowed_values",
            "channel",
            1,
        ),
        (
            lambda df: df.assign(product_id=["A", "A", "A", "B"]),
            "primary_key",
            "date+product_id",
            1,
        ),
    ],
    ids=[
        "int-as-float",
        "non-str",
        "date-with-time",
        "null",
        "range-min",
        "float-range",
        "allowed",
        "pk",
    ],
)
def test_schema_violations_are_counted(
    mutate: Callable[[pd.DataFrame], pd.DataFrame], check: str, field: str, violations: int
) -> None:
    report = validate_dataset(make_sales(mutate(sales_frame())))
    assert not report.passed
    assert result_for(report, check, field) == (CheckStatus.FAILED, violations)


def test_range_is_skipped_when_dtype_is_wrong() -> None:
    frame = sales_frame().assign(quantity=["3", "0", "5", "1"])
    report = validate_dataset(make_sales(frame))
    assert result_for(report, "range", "quantity")[0] is CheckStatus.SKIPPED


def test_foreign_key_skipped_without_reference_and_checked_with_it() -> None:
    sales = make_sales(sales_frame().assign(product_id=["A", "B", "A", "Z"]))
    alone = validate_dataset(sales)
    assert result_for(alone, "foreign_key", "product_id")[0] is CheckStatus.SKIPPED
    assert alone.passed  # skipped is not a failure, but it is visible
    with_ref = validate_dataset(sales, references={"test.product": make_products()})
    assert result_for(with_ref, "foreign_key", "product_id") == (CheckStatus.FAILED, 1)


# --- explicit constraints ---------------------------------------------------------------------

OPS_SCHEMA = DatasetSchema(
    schema_id="test.supplier",
    schema_version="1.0.0",
    fields=(
        FieldSpec(name="supplier_id", dtype=DType.STR),
        FieldSpec(name="lead_time_mean_days", dtype=DType.FLOAT),
        FieldSpec(name="lead_time_std_days", dtype=DType.FLOAT, nullable=True),
        FieldSpec(name="product_id", dtype=DType.STR),
    ),
)


def suppliers(**columns: list[object]) -> pd.DataFrame:
    base: dict[str, list[object]] = {
        "supplier_id": ["S1", "S2", "S3"],
        "lead_time_mean_days": [3.0, 5.0, 7.0],
        "lead_time_std_days": [1.0, 2.0, None],
        "product_id": ["A", "B", "A"],
    }
    return pd.DataFrame(base | columns)


def validate_suppliers(frame: pd.DataFrame, constraint: Constraint) -> ValidationReport:
    dataset = build_dataset(
        dataset_id="suppliers",
        version="1",
        schema=OPS_SCHEMA,
        data=frame,
        source=SOURCE,
        lineage=Lineage(),
    )
    return validate_dataset(dataset, [constraint], references={"test.product": make_products()})


@pytest.mark.parametrize(
    ("constraint", "good", "bad", "violations"),
    [
        (
            RangeConstraint(field="lead_time_mean_days", min=1, max=6),
            {"lead_time_mean_days": [3.0, 5.0, 6.0]},
            {},
            1,
        ),
        (
            RelationConstraint(left="lead_time_std_days", op="<=", right="lead_time_mean_days"),
            {},
            {"lead_time_std_days": [1.0, 9.0, None]},
            1,
        ),
        (
            IntegerConstraint(field="lead_time_mean_days"),
            {},
            {"lead_time_mean_days": [3.5, 5.0, 7.25]},
            2,
        ),
        (UniqueConstraint(fields=("supplier_id",)), {}, {"supplier_id": ["S1", "S1", "S3"]}, 1),
        (
            NotNullConstraint(field="lead_time_std_days"),
            {"lead_time_std_days": [1.0, 2.0, 3.0]},
            {},
            1,
        ),
        (
            ForeignKeyConstraint(
                fields=("product_id",), ref_schema_id="test.product", ref_fields=("product_id",)
            ),
            {},
            {"product_id": ["A", "X", "Y"]},
            2,
        ),
    ],
    ids=["range", "relation", "integer", "unique", "not-null", "foreign-key"],
)
def test_constraints_pass_and_fail(
    constraint: Constraint,
    good: dict[str, list[object]],
    bad: dict[str, list[object]],
    violations: int,
) -> None:
    assert validate_suppliers(suppliers(**good), constraint).passed
    report = validate_suppliers(suppliers(**bad), constraint)
    assert not report.passed
    assert report.failures[-1].check == constraint.kind
    assert report.failures[-1].violations == violations


def test_constraint_on_unknown_field_fails() -> None:
    report = validate_suppliers(suppliers(), NotNullConstraint(field="nope"))
    assert report.failures and report.failures[0].message == "unknown field"


def test_constraint_set_json_round_trip() -> None:
    constraints = ConstraintSet(
        constraints=(
            RangeConstraint(field="quantity", min=0),
            RelationConstraint(left="a", op="<", right="b"),
            ForeignKeyConstraint(fields=("p",), ref_schema_id="x", ref_fields=("p",)),
        )
    )
    assert ConstraintSet.model_validate_json(constraints.model_dump_json()) == constraints
    parsed: Constraint = TypeAdapter(Constraint).validate_python({"kind": "integer", "field": "q"})
    assert isinstance(parsed, IntegerConstraint)


def test_report_json_includes_passed_flag() -> None:
    report = validate_dataset(make_sales(sales_frame().assign(quantity=[3, -1, 5, 1])))
    assert '"passed":false' in report.model_dump_json()


# --- bundle -----------------------------------------------------------------------------------


def test_bundle_validation_resolves_foreign_keys() -> None:
    bundle = DatasetBundle(
        "retail", "1", {"sales": make_sales(), "products": make_products()}, SOURCE
    )
    report = validate_bundle(bundle, {"sales": [RangeConstraint(field="quantity", max=10)]})
    assert report.passed and not report.skipped
    assert result_for(report, "foreign_key", "product_id")[0] is CheckStatus.PASSED


def test_bundle_validation_flags_constraints_for_unknown_table() -> None:
    bundle = DatasetBundle("retail", "1", {"sales": make_sales()}, SOURCE)
    report = validate_bundle(bundle, {"nope": [NotNullConstraint(field="x")]})
    assert not report.passed
