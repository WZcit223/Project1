"""Validation results."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field


class CheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    """The check could not run (e.g. referenced table not supplied); never counts as passed."""


class CheckResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check: str
    """Check kind, e.g. ``dtype``, ``not_null``, ``range``, ``primary_key``, ``foreign_key``."""
    target: str
    """What was checked, e.g. ``test.sales.quantity``."""
    status: CheckStatus
    violations: int = Field(default=0, ge=0)
    """Number of offending rows (0 unless failed)."""
    message: str = ""


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str
    """What was validated, e.g. ``sales@1``."""
    results: tuple[CheckResult, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> bool:
        """True when no check failed. Skipped checks are listed but do not fail the report."""
        return all(r.status is not CheckStatus.FAILED for r in self.results)

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        return tuple(r for r in self.results if r.status is CheckStatus.FAILED)

    @property
    def skipped(self) -> tuple[CheckResult, ...]:
        return tuple(r for r in self.results if r.status is CheckStatus.SKIPPED)
