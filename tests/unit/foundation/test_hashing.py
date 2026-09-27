"""Tests for industrial_ai.foundation.provenance.hashing."""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from industrial_ai.foundation.provenance import content_hash, file_hash


def sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2016-01-01", "2016-01-02", "2016-01-03"]),
            "product_id": ["A", "B", None],
            "quantity": np.array([1, 0, 5], dtype="int64"),
            "price": [1.5, np.nan, 2.0],
            "promo": [True, False, True],
        }
    )


def test_hash_is_deterministic_and_prefixed() -> None:
    assert content_hash(sample()) == content_hash(sample())
    assert content_hash(sample()).startswith("sha256:")


def test_row_index_is_ignored() -> None:
    assert content_hash(sample().set_axis([10, 20, 30])) == content_hash(sample())


def test_column_order_is_ignored() -> None:
    df = sample()
    assert content_hash(df[list(reversed(df.columns))]) == content_hash(df)


def test_physical_dtype_variants_hash_equal() -> None:
    df = sample()
    variant = df.assign(
        quantity=df["quantity"].astype("int32"),
        product_id=df["product_id"].astype("object"),
        price=df["price"].astype("Float64"),
    )
    assert content_hash(variant) == content_hash(df)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda df: df.assign(quantity=[1, 0, 6]),
        lambda df: df.assign(product_id=["A", "B", "C"]),
        lambda df: df.iloc[::-1],
        lambda df: df.rename(columns={"price": "unit_price"}),
        lambda df: df.iloc[:2],
        lambda df: df.assign(quantity=df["quantity"].astype("float64")),
    ],
    ids=["value", "null-filled", "row-order", "column-name", "row-count", "type-family"],
)
def test_any_content_change_changes_hash(mutate: Callable[[pd.DataFrame], pd.DataFrame]) -> None:
    assert content_hash(mutate(sample())) != content_hash(sample())


def test_parquet_round_trip_preserves_hash(tmp_path: Path) -> None:
    path = tmp_path / "t.parquet"
    df = sample().assign(category=pd.Categorical(["x", "y", "x"]))
    df.to_parquet(path, index=False)
    assert content_hash(pd.read_parquet(path)) == content_hash(df)


def test_empty_frame_hashes() -> None:
    empty = pd.DataFrame({"a": pd.Series([], dtype="int64")})
    assert content_hash(empty) != content_hash(pd.DataFrame({"b": pd.Series([], dtype="int64")}))


def test_file_hash() -> None:
    assert file_hash(b"abc") == (
        "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
