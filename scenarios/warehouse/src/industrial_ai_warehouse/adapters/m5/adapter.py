"""M5 adapter: M5-layout CSV files → canonical retail :class:`DatasetBundle` (ADR-003).

Input directory: ``calendar.csv``, ``sell_prices.csv``, one sales file
(``sales_train_evaluation.csv`` preferred, else ``sales_train_validation.csv``) and optionally
``SOURCE.json`` (written by the subset script or the fixture generator). Intended for subsets
(e.g. one store × one department); unpivoting all 30,490 M5 series needs several GB of memory.

Conversions (recorded in provenance): wide daily sales → long rows; M5 ``wday`` (1 = Saturday) →
ISO weekday (1 = Monday), cross-checked against the dates; up to two events per day → event rows;
``snap_<STATE>`` columns → ``retail.calendar_snap`` rows. Output tables are sorted by primary key,
so the same input always yields the same content hashes. Table ``created_at`` is taken from
``SOURCE.json``, which keeps the conversion fully deterministic.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from industrial_ai.core.errors import IngestionError
from industrial_ai.foundation.datasets import (
    Dataset,
    DatasetBundle,
    DatasetSchema,
    SourceInfo,
    SourceType,
    build_dataset,
)
from industrial_ai.foundation.provenance import (
    ComponentRef,
    Lineage,
    TransformationStep,
    file_hash,
)
from industrial_ai_warehouse.adapters.m5.source import (
    CALENDAR_FILE,
    PRICES_FILE,
    SALES_FILES,
    M5Source,
)
from industrial_ai_warehouse.schemas.retail import RETAIL_SCHEMAS

ADAPTER_ID = "m5"
ADAPTER_VERSION = "1.0.0"
REGION_NAMES = {"CA": "California", "TX": "Texas", "WI": "Wisconsin"}
_CALENDAR_COLUMNS = ("date", "wm_yr_wk", "wday", "month", "year", "d")
_EVENT_COLUMNS = (("event_name_1", "event_type_1"), ("event_name_2", "event_type_2"))
_SALES_ID_COLUMNS = ("item_id", "dept_id", "cat_id", "store_id", "state_id")
_PRICE_COLUMNS = ("store_id", "item_id", "wm_yr_wk", "sell_price")


class M5Adapter:
    """Converts M5 (or an M5-layout subset / fixture) into the canonical retail model."""

    adapter_id = ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    description = "M5 Forecasting Accuracy CSV files → canonical retail-demand bundle"

    def load(self, source: Path) -> DatasetBundle:
        """Load and convert the M5 files in ``source``.

        Raises:
            IngestionError: missing files or columns, or inconsistent calendar data.
        """
        info = M5Source.read(source) or _default_source(source)
        sales_path = _sales_file(source)
        calendar_path, prices_path = source / CALENDAR_FILE, source / PRICES_FILE
        for path in (calendar_path, prices_path):
            if not path.is_file():
                raise IngestionError(f"{source}: missing {path.name}")
        hashes = {
            p.name: file_hash(p.read_bytes()) for p in (calendar_path, prices_path, sales_path)
        }

        calendar_raw = _read(calendar_path, _CALENDAR_COLUMNS)
        sales_raw = _read(sales_path, _SALES_ID_COLUMNS)
        prices_raw = _read(prices_path, _PRICE_COLUMNS)
        tables = _convert(calendar_raw, sales_raw, prices_raw)

        builder = _Builder(info, hashes, sales_path.name)
        steps = {
            "calendar": [
                TransformationStep(
                    step="reencode_weekday",
                    details={"from": "M5 wday (1=Saturday)", "to": "ISO weekday (1=Monday)"},
                )
            ],
            "calendar_event": [TransformationStep(step="events_to_rows")],
            "calendar_snap": [TransformationStep(step="snap_columns_to_rows")],
            "sales": [
                TransformationStep(
                    step="unpivot_daily_sales",
                    details={"days": int(sum(c.startswith("d_") for c in sales_raw.columns))},
                )
            ],
        }
        datasets = {
            name: builder.dataset(name, RETAIL_SCHEMAS[name], frame, steps.get(name, []))
            for name, frame in tables.items()
        }
        return DatasetBundle(
            bundle_id=info.dataset_id,
            version=info.version,
            tables=datasets,
            source=builder.source_info(info.dataset_name),
            lineage=builder.lineage([]),
        )


# --- reading ----------------------------------------------------------------------------------


def _default_source(source: Path) -> M5Source:
    """Attribution for a directory without SOURCE.json: assumed to be original Kaggle files."""
    return M5Source(
        dataset_id="m5",
        source_type=SourceType.REFERENCE,
        dataset_name=f"M5 files in {source.name}",
        created_at=datetime.now(UTC),
        created_by=f"{ADAPTER_ID} adapter {ADAPTER_VERSION} (no SOURCE.json found)",
        notes="Download date and subset filters unknown: SOURCE.json was not present.",
    )


def _sales_file(source: Path) -> Path:
    for name in SALES_FILES:
        if (source / name).is_file():
            return source / name
    raise IngestionError(f"{source}: missing sales file (expected one of {list(SALES_FILES)})")


def _read(path: Path, required: Sequence[str]) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise IngestionError(f"{path.name}: missing columns {missing}")
    return frame


# --- conversion -------------------------------------------------------------------------------


def _convert(
    calendar: pd.DataFrame, sales: pd.DataFrame, prices: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    dates = pd.to_datetime(calendar["date"], format="%Y-%m-%d")
    iso_weekday = dates.dt.dayofweek + 1
    expected_iso = (calendar["wday"] + 4) % 7 + 1  # M5: 1=Sat, 2=Sun, 3=Mon … 7=Fri
    if (iso_weekday != expected_iso).any():
        raise IngestionError(f"{CALENDAR_FILE}: 'wday' does not match the dates")

    regions = sorted(sales["state_id"].unique())
    stores = sales[["store_id", "state_id"]].drop_duplicates()
    day_columns = [c for c in sales.columns if c.startswith("d_")]
    unknown_days = sorted(set(day_columns) - set(calendar["d"]))
    if unknown_days:
        raise IngestionError(f"sales days not in {CALENDAR_FILE}: {unknown_days[:5]}")
    date_of_day = dict(zip(calendar["d"], dates, strict=True))

    long_sales = sales.melt(
        id_vars=["item_id", "store_id"], value_vars=day_columns, var_name="d", value_name="quantity"
    )
    series = set(zip(sales["item_id"], sales["store_id"], strict=True))
    price_rows = prices[
        [(i, s) in series for i, s in zip(prices["item_id"], prices["store_id"], strict=True)]
    ]

    return {
        "region": pd.DataFrame(
            {"region_id": regions, "name": [REGION_NAMES.get(r, r) for r in regions]}
        ),
        "store": _sorted(stores.rename(columns={"state_id": "region_id"}), ["store_id"]),
        "category": _sorted(
            sales[["cat_id"]].drop_duplicates().rename(columns={"cat_id": "category_id"}),
            ["category_id"],
        ),
        "department": _sorted(
            sales[["dept_id", "cat_id"]]
            .drop_duplicates()
            .rename(columns={"dept_id": "department_id", "cat_id": "category_id"}),
            ["department_id"],
        ),
        "product": _sorted(
            sales[["item_id", "dept_id", "cat_id"]]
            .drop_duplicates()
            .rename(
                columns={
                    "item_id": "product_id",
                    "dept_id": "department_id",
                    "cat_id": "category_id",
                }
            ),
            ["product_id"],
        ),
        "calendar": pd.DataFrame(
            {
                "date": dates,
                "week_id": calendar["wm_yr_wk"].astype("int64"),
                "weekday": iso_weekday.astype("int64"),
                "month": calendar["month"].astype("int64"),
                "year": calendar["year"].astype("int64"),
            }
        ),
        "calendar_event": _events(calendar, dates),
        "calendar_snap": _snap(calendar, dates, regions),
        "sales": _sorted(
            pd.DataFrame(
                {
                    "date": long_sales["d"].map(date_of_day),
                    "product_id": long_sales["item_id"],
                    "store_id": long_sales["store_id"],
                    "quantity": long_sales["quantity"].astype("int64"),
                }
            ),
            ["date", "product_id", "store_id"],
        ),
        "price": _sorted(
            pd.DataFrame(
                {
                    "week_id": price_rows["wm_yr_wk"].astype("int64"),
                    "product_id": price_rows["item_id"],
                    "store_id": price_rows["store_id"],
                    "unit_price": price_rows["sell_price"].astype("float64"),
                }
            ),
            ["week_id", "product_id", "store_id"],
        ),
    }


def _events(calendar: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    parts = []
    for name_col, type_col in _EVENT_COLUMNS:
        if name_col not in calendar.columns:
            continue
        part = pd.DataFrame(
            {"date": dates, "event_name": calendar[name_col], "event_type": calendar[type_col]}
        )
        parts.append(part[part["event_name"].notna()])
    events = (
        pd.concat(parts, ignore_index=True)
        if parts
        else pd.DataFrame(
            {"date": pd.Series(dtype="datetime64[ns]"), "event_name": [], "event_type": []}
        )
    )
    events["event_type"] = events["event_type"].astype("category")
    return _sorted(events, ["date", "event_name"])


def _snap(calendar: pd.DataFrame, dates: pd.Series, regions: Sequence[str]) -> pd.DataFrame:
    parts = []
    for region in regions:
        column = f"snap_{region}"
        if column not in calendar.columns:
            raise IngestionError(f"{CALENDAR_FILE}: missing column {column!r} for region {region}")
        parts.append(
            pd.DataFrame(
                {"date": dates, "region_id": region, "snap_active": calendar[column].astype(bool)}
            )
        )
    return _sorted(pd.concat(parts, ignore_index=True), ["date", "region_id"])


def _sorted(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return frame.sort_values(keys, kind="stable").reset_index(drop=True)


# --- dataset construction ---------------------------------------------------------------------


class _Builder:
    """Builds each canonical table with shared attribution and per-table provenance."""

    def __init__(self, info: M5Source, file_hashes: dict[str, str], sales_file: str) -> None:
        self._info = info
        self._file_hashes = file_hashes
        self._sales_file = sales_file

    def source_info(self, name: str) -> SourceInfo:
        info = self._info
        return SourceInfo(
            name=name,
            description=info.notes,
            source_type=info.source_type,
            source=info.source,
            source_url=info.source_url or None,
            download_date=info.download_date,
            license_notes=info.license_notes,
            tags=("m5",),
        )

    def lineage(self, steps: Sequence[TransformationStep]) -> Lineage:
        ingest = TransformationStep(
            step="ingest",
            details={
                "files": dict(sorted(self._file_hashes.items())),
                "sales_file": self._sales_file,
                "original_files": dict(sorted(self._info.source_files.items())),
            },
        )
        return Lineage(
            component=ComponentRef(id=ADAPTER_ID, version=ADAPTER_VERSION),
            parameters={"subset_filters": self._info.filters.model_dump(mode="json")},
            transformations=(ingest, *steps),
        )

    def dataset(
        self,
        table: str,
        schema: DatasetSchema,
        frame: pd.DataFrame,
        steps: Sequence[TransformationStep],
    ) -> Dataset:
        return build_dataset(
            dataset_id=f"{self._info.dataset_id}.{table}",
            version=self._info.version,
            schema=schema,
            data=frame,
            source=self.source_info(f"{self._info.dataset_name} — {table}"),
            lineage=self.lineage(steps),
            created_at=self._info.created_at,
        )
