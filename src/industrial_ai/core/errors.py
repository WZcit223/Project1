"""Framework error hierarchy.

All framework errors derive from :class:`IndustrialAIError` so callers (e.g. the API layer)
can map them to responses without catching unrelated exceptions.
"""


class IndustrialAIError(Exception):
    """Base class for all framework errors."""


class ConfigurationError(IndustrialAIError):
    """Invalid or missing configuration."""
