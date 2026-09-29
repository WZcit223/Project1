"""Extract a small M5 subset from the full Kaggle files, for local use and upload.

Example (defaults: store CA_1, department FOODS_3, top 50 items):

    uv run python scripts/make_m5_subset.py --input ~/Downloads/m5-forecasting-accuracy \\
        --download-date 2026-09-20

Writes calendar.csv, sell_prices.csv, the sales file and SOURCE.json to data/raw/m5_subset/
(git-ignored). The output is real M5 data: do not commit or redistribute it.
"""

import argparse
from datetime import date
from pathlib import Path

from industrial_ai_warehouse.adapters.m5.source import SubsetFilters
from industrial_ai_warehouse.adapters.m5.subset import make_subset

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "m5_subset"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input", type=Path, required=True, help="folder with the Kaggle M5 CSVs")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--store", action="append", dest="stores", help="repeatable; default CA_1")
    parser.add_argument(
        "--department", action="append", dest="departments", help="repeatable; default FOODS_3"
    )
    parser.add_argument("--category", action="append", dest="categories", help="repeatable")
    parser.add_argument("--top-n", type=int, default=50, help="0 keeps all matching items")
    parser.add_argument("--download-date", type=date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument("--dataset-id", help="default derived from the filters")
    args = parser.parse_args()

    filters = SubsetFilters(
        stores=tuple(args.stores or ["CA_1"]),
        departments=tuple(args.departments or ([] if args.categories else ["FOODS_3"])),
        categories=tuple(args.categories or []),
        top_n=args.top_n or None,
    )
    record = make_subset(
        args.input,
        args.output,
        filters,
        download_date=args.download_date,
        dataset_id=args.dataset_id,
    )
    print(f"wrote {record.dataset_id} to {args.output}\n{record.notes}")


if __name__ == "__main__":
    main()
