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
