"""Tests for industrial_ai.core.versioning."""

import pytest

from industrial_ai.core.errors import InvalidVersionError
from industrial_ai.core.versioning import SemVer, parse_version


def test_parse_and_format() -> None:
    assert parse_version("1.2.3") == SemVer(1, 2, 3)
    assert str(parse_version("10.0.7")) == "10.0.7"


def test_versions_compare_numerically() -> None:
    assert parse_version("1.10.0") > parse_version("1.9.9")
    assert parse_version("2.0.0") > parse_version("1.99.99")


@pytest.mark.parametrize(
    "bad", ["", "1", "1.2", "1.2.3.4", "v1.2.3", "01.2.3", "1.2.3-rc1", "a.b.c"]
)
def test_invalid_versions_are_rejected(bad: str) -> None:
    with pytest.raises(InvalidVersionError):
        parse_version(bad)
