"""M5 file layout constants and the ``SOURCE.json`` attribution record.

``SOURCE.json`` sits next to M5-layout CSV files and records where they came from: the original
Kaggle files (with hashes), the subset filters applied, and licence notes. The adapter copies it
into dataset metadata and provenance, so attribution is never lost.
"""

import json
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from industrial_ai.foundation.datasets import SourceType

M5_NAME = "M5 Forecasting Accuracy"
M5_URL = "https://www.kaggle.com/competitions/m5-forecasting-accuracy/data"
M5_LICENSE = "Kaggle competition data: competition rules apply; do not redistribute."
CALENDAR_FILE = "calendar.csv"
PRICES_FILE = "sell_prices.csv"
SALES_FILES = ("sales_train_evaluation.csv", "sales_train_validation.csv")
"""Preferred first: the evaluation file is a superset of the validation file."""
SOURCE_FILE = "SOURCE.json"


class SubsetFilters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stores: tuple[str, ...] = ()
    departments: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    top_n: int | None = Field(default=None, ge=1)
    """Keep the ``top_n`` items with the highest total sales in the selected stores."""


class M5Source(BaseModel):
    """Contents of ``SOURCE.json``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    version: str = "1"
    source_type: SourceType
    source: str = M5_NAME
    source_url: str = M5_URL
    dataset_name: str
    download_date: date | None = None
    """When the original Kaggle files were downloaded (``None`` = not stated by the user)."""
    license_notes: str = M5_LICENSE
    filters: SubsetFilters = SubsetFilters()
    source_files: dict[str, str] = Field(default_factory=dict)
    """Original file name → ``sha256:`` hash of the file the subset was taken from."""
    created_at: datetime
    created_by: str
    notes: str = ""

    def write(self, directory: Path) -> Path:
        path = directory / SOURCE_FILE
        path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def read(cls, directory: Path) -> "M5Source | None":
        path = directory / SOURCE_FILE
        if not path.is_file():
            return None
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
