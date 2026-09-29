"""Deterministic content hashing of tabular data.

The hash identifies *what the data is*, independent of how it is held in memory:

- the row index is ignored (only values count);
- column order is ignored (columns are hashed in sorted name order);
- physical dtypes are normalised to a logical family (e.g. ``int32``/``int64`` → ``integer``,
  ``object``/``str`` → ``string``), so a Parquet round trip does not change the hash;
- row order **does** count: generators and adapters produce rows in a deterministic order.

Format: ``"sha256:<hex>"``.
"""

import hashlib

import pandas as pd
from pandas.api import types as ptypes

HASH_PREFIX = "sha256:"


def logical_dtype(series: pd.Series) -> str:
    """Logical type family of a column, stable across pandas storage choices."""
    dtype = series.dtype
    if isinstance(dtype, pd.CategoricalDtype):
        return "category"
    if ptypes.is_bool_dtype(dtype):
        return "bool"
    if ptypes.is_integer_dtype(dtype):
        return "integer"
    if ptypes.is_float_dtype(dtype):
        return "float"
    if ptypes.is_datetime64_any_dtype(dtype):
        return "datetime"
    if ptypes.is_string_dtype(dtype) or ptypes.is_object_dtype(dtype):
        return "string"
    return str(dtype)


def _normalised_values(series: pd.Series) -> pd.Series:
    """Values in a representation whose hash does not depend on the physical dtype."""
    family = logical_dtype(series)
    if family == "category":
        return series.astype("object").astype("str").where(series.notna(), None)
    if family == "integer":
        return series.astype("Int64")
    if family == "float":
        return series.astype("Float64")
    if family == "bool":
        return series.astype("boolean")
    if family == "datetime":
        return series.astype("datetime64[ns]")
    if family == "string":
        return series.astype("object").where(series.notna(), None)
    return series


def content_hash(data: pd.DataFrame) -> str:
    """SHA-256 content hash of a DataFrame (see module docstring for the exact semantics)."""
    digest = hashlib.sha256()
    digest.update(f"rows={len(data)}\n".encode())
    for column in sorted(data.columns, key=str):
        series = data[column]
        digest.update(f"column={column}|type={logical_dtype(series)}\n".encode())
        values = _normalised_values(series.reset_index(drop=True))
        row_hashes = pd.util.hash_pandas_object(values, index=False).to_numpy()
        digest.update(row_hashes.tobytes())
    return HASH_PREFIX + digest.hexdigest()


def file_hash(content: bytes) -> str:
    """SHA-256 of raw file bytes, in the same ``"sha256:<hex>"`` format."""
    return HASH_PREFIX + hashlib.sha256(content).hexdigest()
