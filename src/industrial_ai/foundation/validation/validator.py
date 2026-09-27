"""Schema and constraint validation of datasets and bundles (docs/validation.md, Level 2).

Validation never modifies data and never raises for bad data: every problem becomes a failed
:class:`CheckResult` with a count of offending rows. Checks that cannot run are reported as
``skipped`` rather than silently passed.
"""

import operator
from collections.abc import Callable, Mapping, Sequence

import pandas as pd
from pandas.api import types as ptypes

from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetBundle,
    DatasetSchema,
    DType,
    FieldSpec,
)
from industrial_ai.foundation.validation.constraints import (
    Constraint,
    ConstraintSet,
    ForeignKeyConstraint,
    IntegerConstraint,
    NotNullConstraint,
    RangeConstraint,
    RelationConstraint,
    UniqueConstraint,
)
from industrial_ai.foundation.validation.report import CheckResult, CheckStatus, ValidationReport

_OPERATORS: dict[str, Callable[[pd.Series, pd.Series], pd.Series]] = {
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    ">=": operator.ge,
    ">": operator.gt,
}


def validate_dataset(
    dataset: Dataset,
    constraints: ConstraintSet | Sequence[Constraint] = (),
    references: Mapping[str, Dataset] | None = None,
) -> ValidationReport:
    """Validate one dataset against its schema and extra ``constraints``.

    ``references`` maps ``schema_id`` → dataset for foreign-key checks; foreign keys whose
    referenced table is not supplied are reported as skipped.
    """
    extra = (
        constraints.constraints if isinstance(constraints, ConstraintSet) else tuple(constraints)
    )
    results = _check_dataset(dataset, extra, references or {})
    return ValidationReport(subject=dataset.ref, results=tuple(results))


def validate_bundle(
    bundle: DatasetBundle,
    constraints: Mapping[str, ConstraintSet | Sequence[Constraint]] | None = None,
) -> ValidationReport:
    """Validate every table of a bundle; foreign keys resolve against the bundle's tables.

    ``constraints`` maps table name → extra constraints for that table.
    """
    references = {table.schema.schema_id: table for table in bundle.tables.values()}
    per_table = constraints or {}
    unknown = sorted(set(per_table) - set(bundle.tables))
    results: list[CheckResult] = [
        CheckResult(
            check="constraints",
            target=f"{bundle.ref}.{name}",
            status=CheckStatus.FAILED,
            message="constraints given for a table that is not in the bundle",
        )
        for name in unknown
    ]
    for name in sorted(bundle.tables):
        extra = per_table.get(name, ())
        extra_tuple = extra.constraints if isinstance(extra, ConstraintSet) else tuple(extra)
        results.extend(_check_dataset(bundle.tables[name], extra_tuple, references))
    return ValidationReport(subject=bundle.ref, results=tuple(results))


# --- dataset-level ----------------------------------------------------------------------------


def _check_dataset(
    dataset: Dataset, extra: Sequence[Constraint], references: Mapping[str, Dataset]
) -> list[CheckResult]:
    schema, data = dataset.schema, dataset.data
    results: list[CheckResult] = []
    typed_ok: set[str] = set()
    for spec in schema.fields:
        type_result = _check_dtype(schema, spec, data[spec.name])
        results.append(type_result)
        if type_result.status is CheckStatus.PASSED:
            typed_ok.add(spec.name)
        results.extend(_check_field_values(schema, spec, data[spec.name], typed_ok))
    if schema.primary_key:
        results.append(_check_unique(schema, data, schema.primary_key, check="primary_key"))
    for fk in schema.foreign_keys:
        results.append(
            _check_foreign_key(schema, data, fk.fields, fk.ref_schema_id, fk.ref_fields, references)
        )
    results.extend(_check_constraint(schema, data, c, typed_ok, references) for c in extra)
    return results


def _target(schema: DatasetSchema, *fields: str) -> str:
    return f"{schema.schema_id}.{'+'.join(fields)}"


def _result(check: str, target: str, violations: int, message: str = "") -> CheckResult:
    status = CheckStatus.FAILED if violations else CheckStatus.PASSED
    return CheckResult(
        check=check, target=target, status=status, violations=violations, message=message
    )


def _skipped(check: str, target: str, message: str) -> CheckResult:
    return CheckResult(check=check, target=target, status=CheckStatus.SKIPPED, message=message)


def _failed(check: str, target: str, message: str, violations: int = 0) -> CheckResult:
    return CheckResult(
        check=check,
        target=target,
        status=CheckStatus.FAILED,
        violations=violations,
        message=message,
    )


# --- field checks -----------------------------------------------------------------------------


def _is_str_values(values: pd.Series) -> int:
    """Number of non-null values that are not ``str``."""
    return int((~values.dropna().map(lambda v: isinstance(v, str))).sum())


def _check_dtype(schema: DatasetSchema, spec: FieldSpec, column: pd.Series) -> CheckResult:
    target = _target(schema, spec.name)
    dtype = column.dtype
    non_null = int(column.notna().sum())
    expected = spec.dtype
    if expected is DType.INT:
        ok = ptypes.is_integer_dtype(dtype) and not ptypes.is_bool_dtype(dtype)
    elif expected is DType.FLOAT:
        ok = ptypes.is_numeric_dtype(dtype) and not ptypes.is_bool_dtype(dtype)
    elif expected is DType.BOOL:
        ok = ptypes.is_bool_dtype(dtype)
    elif expected in (DType.DATE, DType.DATETIME):
        ok = ptypes.is_datetime64_any_dtype(dtype)
        if ok and expected is DType.DATE:
            times = pd.to_datetime(column.dropna())
            bad = int((times != times.dt.normalize()).sum())
            return _result("dtype", target, bad, "date values must not have a time component")
    elif expected is DType.CATEGORY and isinstance(dtype, pd.CategoricalDtype):
        ok = True
    else:  # STR, or CATEGORY stored as strings
        if not (ptypes.is_string_dtype(dtype) or ptypes.is_object_dtype(dtype)):
            ok = False
        else:
            return _result("dtype", target, _is_str_values(column), f"expected {expected} values")
    if ok:
        return _result("dtype", target, 0)
    return _failed("dtype", target, f"expected {expected}, found pandas dtype {dtype}", non_null)


def _check_field_values(
    schema: DatasetSchema, spec: FieldSpec, column: pd.Series, typed_ok: set[str]
) -> list[CheckResult]:
    target = _target(schema, spec.name)
    results: list[CheckResult] = []
    if not spec.nullable:
        results.append(_result("not_null", target, int(column.isna().sum())))
    if spec.min is not None or spec.max is not None:
        if spec.name in typed_ok:
            results.append(_range_result(target, column, spec.min, spec.max))
        else:
            results.append(_skipped("range", target, "skipped: column has the wrong dtype"))
    if spec.allowed_values is not None:
        allowed = set(spec.allowed_values)
        values = column.dropna().astype("object").map(str)
        results.append(
            _result(
                "allowed_values",
                target,
                int((~values.isin(allowed)).sum()),
                f"allowed: {sorted(allowed)}",
            )
        )
    return results


def _range_result(
    target: str, column: pd.Series, low: float | None, high: float | None
) -> CheckResult:
    values = column.dropna()
    bad = pd.Series(False, index=values.index)
    if low is not None:
        bad |= values < low
    if high is not None:
        bad |= values > high
    return _result("range", target, int(bad.sum()), f"allowed range [{low}, {high}]")


# --- multi-row checks -------------------------------------------------------------------------


def _check_unique(
    schema: DatasetSchema, data: pd.DataFrame, fields: Sequence[str], check: str
) -> CheckResult:
    target = _target(schema, *fields)
    missing = [f for f in fields if f not in data.columns]
    if missing:
        return _failed(check, target, f"unknown fields {missing}")
    duplicates = int(data.duplicated(subset=list(fields), keep="first").sum())
    nulls = int(data[list(fields)].isna().any(axis=1).sum()) if check == "primary_key" else 0
    message = "duplicate keys" if duplicates else ""
    if nulls:
        message = (message + "; " if message else "") + "null key values"
    return _result(check, target, duplicates + nulls, message)


def _check_foreign_key(
    schema: DatasetSchema,
    data: pd.DataFrame,
    fields: Sequence[str],
    ref_schema_id: str,
    ref_fields: Sequence[str],
    references: Mapping[str, Dataset],
) -> CheckResult:
    target = f"{_target(schema, *fields)} -> {ref_schema_id}.{'+'.join(ref_fields)}"
    parent = references.get(ref_schema_id)
    if parent is None:
        return _skipped("foreign_key", target, f"referenced table {ref_schema_id!r} not supplied")
    missing = [f for f in fields if f not in data.columns] + [
        f for f in ref_fields if f not in parent.data.columns
    ]
    if missing:
        return _failed("foreign_key", target, f"unknown fields {missing}")
    child = data[list(fields)].dropna().astype("object")
    keys = pd.MultiIndex.from_frame(
        parent.data[list(ref_fields)].astype("object").set_axis(list(fields), axis=1)
    )
    orphans = int((~pd.MultiIndex.from_frame(child).isin(keys)).sum()) if len(child) else 0
    return _result("foreign_key", target, orphans, "rows reference missing keys" if orphans else "")


def _check_constraint(
    schema: DatasetSchema,
    data: pd.DataFrame,
    constraint: Constraint,
    typed_ok: set[str],
    references: Mapping[str, Dataset],
) -> CheckResult:
    match constraint:
        case RangeConstraint(field=name, min=low, max=high):
            if name not in data.columns:
                return _failed("range", _target(schema, name), "unknown field")
            if not ptypes.is_numeric_dtype(data[name].dtype):
                return _skipped("range", _target(schema, name), "skipped: field is not numeric")
            return _range_result(_target(schema, name), data[name], low, high)
        case NotNullConstraint(field=name):
            if name not in data.columns:
                return _failed("not_null", _target(schema, name), "unknown field")
            return _result("not_null", _target(schema, name), int(data[name].isna().sum()))
        case UniqueConstraint(fields=fields):
            return _check_unique(schema, data, fields, check="unique")
        case IntegerConstraint(field=name):
            if name not in data.columns:
                return _failed("integer", _target(schema, name), "unknown field")
            values = data[name].dropna()
            if not ptypes.is_numeric_dtype(values.dtype):
                return _failed(
                    "integer", _target(schema, name), "field is not numeric", len(values)
                )
            return _result("integer", _target(schema, name), int((values % 1 != 0).sum()))
        case ForeignKeyConstraint(fields=fields, ref_schema_id=ref_id, ref_fields=ref_fields):
            return _check_foreign_key(schema, data, fields, ref_id, ref_fields, references)
        case RelationConstraint(left=left, op=op, right=right):
            target = f"{schema.schema_id}.{left} {op} {right}"
            missing = [f for f in (left, right) if f not in data.columns]
            if missing:
                return _failed("relation", target, f"unknown fields {missing}")
            if not {left, right} <= typed_ok or not all(
                ptypes.is_numeric_dtype(data[f].dtype) for f in (left, right)
            ):
                return _skipped("relation", target, "skipped: fields are not valid numeric columns")
            both = data[[left, right]].dropna()
            holds = _OPERATORS[op](both[left], both[right])
            return _result("relation", target, int((~holds).sum()))
    raise TypeError(f"unsupported constraint {constraint!r}")  # pragma: no cover
