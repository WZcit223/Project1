"""Framework error hierarchy.

All framework errors derive from :class:`IndustrialAIError` so callers (e.g. the API layer)
can map them to responses without catching unrelated exceptions.
"""


class IndustrialAIError(Exception):
    """Base class for all framework errors."""


class ConfigurationError(IndustrialAIError):
    """Invalid or missing configuration."""


class InvalidVersionError(IndustrialAIError, ValueError):
    """A version string is not a valid ``MAJOR.MINOR.PATCH`` semantic version."""


class RegistryError(IndustrialAIError):
    """Base class for plugin registry errors."""


class DuplicatePluginError(RegistryError):
    """A plugin with the same ``(id, version)`` is already registered."""


class PluginNotFoundError(RegistryError, LookupError):
    """No plugin is registered under the requested id (and version)."""


class DatasetError(IndustrialAIError):
    """A dataset is malformed or inconsistent with its schema, metadata or provenance."""


class CatalogError(IndustrialAIError):
    """Base class for dataset catalog errors."""


class DatasetAlreadyRegisteredError(CatalogError):
    """A different dataset is already registered under the same ``(dataset_id, version)``."""


class DatasetNotFoundError(CatalogError, LookupError):
    """No dataset (or bundle) is registered under the requested id and version."""


class IngestionError(DatasetError):
    """An external file cannot be read into a dataset (unreadable, wrong columns, bad values)."""


class GeneratorError(IndustrialAIError):
    """Base class for synthetic data generation errors."""


class GeneratorParameterError(GeneratorError, ValueError):
    """Generator parameters (or size / reference inputs) are invalid."""


class ConstraintViolationError(GeneratorError):
    """Generated data violates its schema or constraints (see the attached report)."""

    def __init__(self, message: str, report: object) -> None:
        super().__init__(message)
        self.report = report


class SimulationError(IndustrialAIError):
    """Base class for simulation errors; a failed run raises instead of returning a result."""


class SimulationInputError(SimulationError, ValueError):
    """The dataset, parameters or upstream results do not satisfy the plugin's requirements."""


class ScenarioError(IndustrialAIError):
    """Base class for scenario specification errors."""


class ScenarioValidationError(ScenarioError, ValueError):
    """A scenario file or specification is malformed, or its parameters fail the pack's model."""
