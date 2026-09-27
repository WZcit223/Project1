"""Dataset adapter protocol (ADR-003): external format → canonical :class:`DatasetBundle`.

Adapters isolate the quirks and licensing of an external dataset (e.g. M5) in one module. The
framework defines only this protocol; concrete adapters live in scenario packs.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from industrial_ai.core.registry import Registry
from industrial_ai.foundation.datasets import DatasetBundle


@runtime_checkable
class DatasetAdapter(Protocol):
    adapter_id: str
    adapter_version: str
    """Semver; bump when the produced canonical data changes for the same input."""
    description: str

    def load(self, source: Path) -> DatasetBundle:
        """Read the external files under ``source``; return canonical data with provenance."""
        ...


def new_adapter_registry() -> Registry[DatasetAdapter]:
    """An empty registry of dataset adapters keyed by ``(adapter_id, adapter_version)``."""
    return Registry("dataset adapter", key=lambda a: (a.adapter_id, a.adapter_version))
