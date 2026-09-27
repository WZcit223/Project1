"""Ingestion: tabular file loaders and the dataset adapter protocol."""

from industrial_ai.foundation.ingestion.adapters import DatasetAdapter, new_adapter_registry
from industrial_ai.foundation.ingestion.loaders import LOADER_ID, LOADER_VERSION, load_table

__all__ = ["LOADER_ID", "LOADER_VERSION", "DatasetAdapter", "load_table", "new_adapter_registry"]
