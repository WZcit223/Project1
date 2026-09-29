"""Semantic versions for plugins, schemas and scenarios.

v0.1 supports plain ``MAJOR.MINOR.PATCH`` only (no pre-release or build metadata), which is
all plugin and scenario versions need. Package versions (e.g. ``0.1.0.dev0``) are not parsed here.
"""

import re
from typing import NamedTuple

from industrial_ai.core.errors import InvalidVersionError

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class SemVer(NamedTuple):
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def parse_version(version: str) -> SemVer:
    """Parse ``"1.2.3"`` into a comparable :class:`SemVer`.

    Raises:
        InvalidVersionError: if ``version`` is not ``MAJOR.MINOR.PATCH``.
    """
    match = _SEMVER.fullmatch(version)
    if match is None:
        raise InvalidVersionError(f"Invalid version {version!r}; expected MAJOR.MINOR.PATCH")
    major, minor, patch = (int(part) for part in match.groups())
    return SemVer(major, minor, patch)
