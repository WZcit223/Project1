"""Standalone M5 subset extractor — needs only Python 3.10+ and pandas (no project checkout).

Produces exactly the same files as ``scripts/make_m5_subset.py`` (calendar.csv, sell_prices.csv,
the sales file and SOURCE.json), for data owners who have the Kaggle files but not the repository.
Keep the output out of Git and do not redistribute it (Kaggle competition rules).

    python3 m5_subset_standalone.py --input DATA/m5-forecasting-accuracy \
        --output DATA/m5_subset --download-date 2026-09-20

Defaults: store CA_1, department FOODS_3, top 50 items by total sales.
"""

import argparse
import hashlib
import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

_UTC = timezone.utc  # noqa: UP017 (datetime.UTC needs Python 3.11; this script supports 3.10)
TOOL_VERSION = "1.0.0"
CALENDAR_FILE = "calendar.csv"
PRICES_FILE = "sell_prices.csv"
SALES_FILES = ("sales_train_evaluation.csv", "sales_train_validation.csv")
M5_NAME = "M5 Forecasting Accuracy"
M5_URL = "https://www.kaggle.com/competitions/m5-forecasting-accuracy/data"
M5_LICENSE = "Kaggle competition data: competition rules apply; do not redistribute."


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def select_sales(
    path: Path,
    stores: list[str],
    departments: list[str],
    categories: list[str],
    top_n: int | None,
    chunksize: int,
) -> pd.DataFrame:
    kept = []
    for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=chunksize):
        mask = pd.Series(True, index=chunk.index)
        if stores:
            mask &= chunk["store_id"].isin(stores)
        if departments:
            mask &= chunk["dept_id"].isin(departments)
        if categories:
            mask &= chunk["cat_id"].isin(categories)
        kept.append(chunk[mask])
    sales = pd.concat(kept, ignore_index=True)
    if sales.empty:
        raise SystemExit("No M5 series match the filters.")
    if top_n is not None:
        days = [c for c in sales.columns if c.startswith("d_")]
        totals = sales[days].apply(pd.to_numeric).sum(axis=1).groupby(sales["item_id"]).sum()
        ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
        top = {item for item, _ in ranked[:top_n]}
        sales = sales[sales["item_id"].isin(top)]
    return sales.reset_index(drop=True)


def select_prices(path: Path, series: set[tuple[str, str]], chunksize: int) -> pd.DataFrame:
    kept = []
    for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=chunksize):
        pairs = zip(chunk["item_id"], chunk["store_id"], strict=True)
        kept.append(chunk[[pair in series for pair in pairs]])
    return pd.concat(kept, ignore_index=True)


def default_dataset_id(parts: list[str], top_n: int | None) -> str:
    suffix = f"_top{top_n}" if top_n else ""
    return ("m5_subset_" + "_".join(p.lower() for p in parts)).rstrip("_") + suffix


def make_subset(
    input_dir: Path,
    output_dir: Path,
    stores: list[str],
    departments: list[str],
    categories: list[str],
    top_n: int | None,
    download_date: date | None,
    dataset_id: str | None = None,
    chunksize: int = 2000,
) -> dict[str, object]:
    sales_path = next((input_dir / n for n in SALES_FILES if (input_dir / n).is_file()), None)
    if sales_path is None:
        raise SystemExit(f"{input_dir}: missing sales file (expected one of {list(SALES_FILES)})")
    for name in (CALENDAR_FILE, PRICES_FILE):
        if not (input_dir / name).is_file():
            raise SystemExit(f"{input_dir}: missing {name}")

    sales = select_sales(sales_path, stores, departments, categories, top_n, chunksize)
    series = set(zip(sales["item_id"], sales["store_id"], strict=True))
    prices = select_prices(input_dir / PRICES_FILE, series, chunksize)

    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(input_dir / CALENDAR_FILE, output_dir / CALENDAR_FILE)
    sales.to_csv(output_dir / sales_path.name, index=False, lineterminator="\n")
    prices.to_csv(output_dir / PRICES_FILE, index=False, lineterminator="\n")

    description = "; ".join(
        [
            f"stores={','.join(stores) or 'all'}",
            f"departments={','.join(departments) or 'all'}",
            f"categories={','.join(categories) or 'all'}",
            f"top_n={top_n or 'all'}",
        ]
    )
    record: dict[str, object] = {
        "created_at": datetime.now(_UTC).isoformat().replace("+00:00", "Z"),
        "created_by": f"industrial_ai_warehouse.adapters.m5.subset {TOOL_VERSION}",
        "dataset_id": dataset_id or default_dataset_id([*stores, *departments, *categories], top_n),
        "dataset_name": f"{M5_NAME} subset ({description})",
        "download_date": download_date.isoformat() if download_date else None,
        "filters": {
            "categories": categories,
            "departments": departments,
            "stores": stores,
            "top_n": top_n,
        },
        "license_notes": M5_LICENSE,
        "notes": (
            f"{len(sales)} series, {len(prices)} price rows. Real M5 data: keep out of Git and "
            "do not redistribute." + ("" if download_date else " Download date not provided.")
        ),
        "source": M5_NAME,
        "source_files": {
            p.name: sha256(p)
            for p in (input_dir / CALENDAR_FILE, input_dir / PRICES_FILE, sales_path)
        },
        "source_type": "reference",
        "source_url": M5_URL,
        "version": "1",
    }
    (output_dir / "SOURCE.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input", type=Path, required=True, help="folder with the Kaggle M5 CSVs")
    parser.add_argument("--output", type=Path, default=Path("m5_subset"))
    parser.add_argument("--store", action="append", dest="stores", help="repeatable; default CA_1")
    parser.add_argument(
        "--department", action="append", dest="departments", help="repeatable; default FOODS_3"
    )
    parser.add_argument("--category", action="append", dest="categories", help="repeatable")
    parser.add_argument("--top-n", type=int, default=50, help="0 keeps all matching items")
    parser.add_argument("--download-date", type=date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument("--dataset-id", help="default derived from the filters")
    args = parser.parse_args()

    record = make_subset(
        args.input,
        args.output,
        stores=args.stores or ["CA_1"],
        departments=args.departments or ([] if args.categories else ["FOODS_3"]),
        categories=args.categories or [],
        top_n=args.top_n or None,
        download_date=args.download_date,
        dataset_id=args.dataset_id,
    )
    print(f"wrote {record['dataset_id']} to {args.output}\n{record['notes']}")


if __name__ == "__main__":
    main()
