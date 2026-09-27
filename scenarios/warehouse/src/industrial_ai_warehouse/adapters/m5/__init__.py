"""M5 Forecasting Accuracy → canonical retail model (ADR-003)."""

from industrial_ai_warehouse.adapters.m5.adapter import ADAPTER_ID, ADAPTER_VERSION, M5Adapter
from industrial_ai_warehouse.adapters.m5.source import M5Source, SubsetFilters

__all__ = ["ADAPTER_ID", "ADAPTER_VERSION", "M5Adapter", "M5Source", "SubsetFilters"]
