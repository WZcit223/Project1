"""Tabular loaders: CSV / Parquet file → :class:`Dataset` with typed columns and provenance.

CSV values are read as text and converted per the schema's logical type. Values that cannot be
converted are **not** turned into missing values silently: loading fails with an
:class:`IngestionError` naming the column and example values. Range and other value rules are
checked separately by :func:`industrial_ai.foundation.validation.validate_dataset`.
"""

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from industrial_ai.core.errors import IngestionError
from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetSchema,
    DType,
    SourceInfo,
    build_dataset,
)
from industrial_ai.foundation.provenance import (
    ComponentRef,
    Lineage,
    TransformationStep,
    file_hash,
)

LOADER_ID = "tabular_loader"
LOADER_VERSION = "1.0.0"
_TRUE = {"true", "1", "yes", "y", "t"}
_FALSE = {"false", "0", "no", "n", "f"}


def load_table(
    path: Path,
    schema: DatasetSchema,
    *,
    dataset_id: str,
    version: str,
    source: SourceInfo,
) -> Dataset:
    """Load a ``.csv`` or ``.parquet`` file whose columns are exactly the schema's fields.

    Raises:
        IngestionError: unsupported format, missing/unexpected columns, or unconvertible values.
    """
    suffix = path.suffix.lower()
    if suffix not in (".csv", ".parquet"):
        raise IngestionError(f"{path.name}: unsupported format {suffix!r} (use .csv or .parquet)")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise IngestionError(f"{path}: cannot read file ({exc})") from exc
    if suffix == ".csv":
        frame = pd.read_csv(path, dtype=str, keep_default_na=True)
        _check_columns(path, frame, schema)
        frame = pd.DataFrame(
            {
                spec.name: _convert(path, spec.name, spec.dtype, frame[spec.name])
                for spec in schema.fields
            }
        )
    else:
        frame = pd.read_parquet(path)
        _check_columns(path, frame, schema)
    lineage = Lineage(
        component=ComponentRef(id=LOADER_ID, version=LOADER_VERSION),
        transformations=(
            TransformationStep(
                step="ingest",
                details={
                    "file": path.name,
                    "format": suffix.lstrip("."),
                    "file_hash": file_hash(raw),
                    "schema_id": schema.schema_id,
                    "schema_version": schema.schema_version,
                },
            ),
        ),
    )
    return build_dataset(
        dataset_id=dataset_id,
        version=version,
        schema=schema,
        data=frame,
        source=source,
        lineage=lineage,
    )


def _check_columns(path: Path, frame: pd.DataFrame, schema: DatasetSchema) -> None:
    missing = sorted(set(schema.field_names) - set(frame.columns))
    extra = sorted(set(map(str, frame.columns)) - set(schema.field_names))
    if missing or extra:
        raise IngestionError(
            f"{path.name}: columns do not match schema {schema.schema_id} "
            f"(missing {missing}, unexpected {extra})"
        )


def _convert(path: Path, name: str, dtype: DType, text: pd.Series) -> pd.Series:
    converted = _CONVERTERS[dtype](text)
    failed = text.notna() & converted.isna()
    if dtype is DType.INT:
        failed |= converted.notna() & (converted % 1 != 0)
    if failed.any():
        examples = text[failed].unique()[:3].tolist()
        raise IngestionError(
            f"{path.name}: column {name!r} has {int(failed.sum())} value(s) that are not "
            f"valid {dtype}, e.g. {examples}"
        )
    if dtype is DType.INT:
        return converted.astype("int64" if converted.notna().all() else "Int64")
    if dtype is DType.BOOL:
        return converted.astype("bool" if converted.notna().all() else "boolean")
    return converted


def _to_bool(text: pd.Series) -> pd.Series:
    lowered = text.str.strip().str.lower()
    result = pd.Series(pd.NA, index=text.index, dtype="boolean")
    result[lowered.isin(_TRUE)] = True
    result[lowered.isin(_FALSE)] = False
    return result


_CONVERTERS: dict[DType, Callable[[pd.Series], pd.Series]] = {
    DType.INT: lambda s: pd.to_numeric(s, errors="coerce"),
    DType.FLOAT: lambda s: pd.to_numeric(s, errors="coerce").astype("float64"),
    DType.BOOL: _to_bool,
    DType.DATE: lambda s: pd.to_datetime(s, errors="coerce", format="ISO8601"),
    DType.DATETIME: lambda s: pd.to_datetime(s, errors="coerce", format="ISO8601"),
    DType.STR: lambda s: s,
    DType.CATEGORY: lambda s: s.astype("category"),
}
