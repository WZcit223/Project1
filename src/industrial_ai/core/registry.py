"""Generic in-process plugin registry keyed by ``(id, version)`` (docs/plugin-spec.md §2).

Each plugin type (generators, simulation plugins, strategies, …) gets its own ``Registry``
instance; the ``key`` function tells the registry where a plugin keeps its id and version, so
plugin protocols keep their own attribute names (e.g. ``generator_id`` / ``generator_version``).
"""

import builtins
from collections.abc import Callable, Iterator
from typing import Generic, TypeVar

from industrial_ai.core.errors import DuplicatePluginError, PluginNotFoundError
from industrial_ai.core.versioning import SemVer, parse_version

T = TypeVar("T")

PluginKey = tuple[str, str]
"""``(plugin_id, version)``."""


class Registry(Generic[T]):
    """Registry of plugins of one kind, discoverable by id and semantic version."""

    def __init__(self, kind: str, key: Callable[[T], PluginKey]) -> None:
        self._kind = kind
        self._key = key
        self._plugins: dict[str, dict[SemVer, T]] = {}

    @property
    def kind(self) -> str:
        return self._kind

    def register(self, plugin: T) -> None:
        """Register a plugin.

        Raises:
            DuplicatePluginError: if the same ``(id, version)`` is already registered.
            InvalidVersionError: if the plugin's version is not ``MAJOR.MINOR.PATCH``.
        """
        plugin_id, version = self._key(plugin)
        semver = parse_version(version)
        versions = self._plugins.setdefault(plugin_id, {})
        if semver in versions:
            raise DuplicatePluginError(
                f"{self._kind} {plugin_id!r} version {version} is already registered"
            )
        versions[semver] = plugin

    def get(self, plugin_id: str, version: str | None = None) -> T:
        """Return the plugin with ``plugin_id``: the given ``version``, or the latest if omitted.

        Raises:
            PluginNotFoundError: if no matching plugin is registered.
        """
        versions = self._plugins.get(plugin_id)
        if not versions:
            raise PluginNotFoundError(f"No {self._kind} registered with id {plugin_id!r}")
        if version is None:
            return versions[max(versions)]
        plugin = versions.get(parse_version(version))
        if plugin is None:
            available = ", ".join(str(v) for v in sorted(versions))
            raise PluginNotFoundError(
                f"{self._kind} {plugin_id!r} has no version {version} (available: {available})"
            )
        return plugin

    def list(self) -> builtins.list[T]:
        """All registered plugins, ordered by id, then version."""
        return [
            self._plugins[plugin_id][semver]
            for plugin_id in sorted(self._plugins)
            for semver in sorted(self._plugins[plugin_id])
        ]

    def keys(self) -> builtins.list[PluginKey]:
        """All registered ``(id, version)`` pairs, ordered by id, then version."""
        return [
            (plugin_id, str(semver))
            for plugin_id in sorted(self._plugins)
            for semver in sorted(self._plugins[plugin_id])
        ]

    def __contains__(self, item: object) -> bool:
        """``"id" in registry`` or ``("id", "1.0.0") in registry``."""
        if isinstance(item, str):
            return item in self._plugins
        if isinstance(item, tuple) and len(item) == 2:
            plugin_id, version = item
            if not isinstance(plugin_id, str) or not isinstance(version, str):
                return False
            try:
                return parse_version(version) in self._plugins.get(plugin_id, {})
            except ValueError:
                return False
        return False

    def __iter__(self) -> Iterator[T]:
        return iter(self.list())

    def __len__(self) -> int:
        return sum(len(versions) for versions in self._plugins.values())
