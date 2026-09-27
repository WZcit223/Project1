"""Declarative, serialisable constraints (docs/synthetic-data-api.md §3).

Constraints add rules beyond what a schema states. They are data, not code: no expression
strings are evaluated, so a constraint set can come from a config file or an LLM proposal and
still be validated safely.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Constraint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RangeConstraint(_Constraint):
    kind: Literal["range"] = "range"
    field: str
    min: float | None = None
    max: float | None = None


class NotNullConstraint(_Constraint):
    kind: Literal["not_null"] = "not_null"
    field: str


class UniqueConstraint(_Constraint):
    kind: Literal["unique"] = "unique"
    fields: tuple[str, ...] = Field(min_length=1)


class IntegerConstraint(_Constraint):
    """Values are integral (useful for float columns that must hold whole units)."""

    kind: Literal["integer"] = "integer"
    field: str


class ForeignKeyConstraint(_Constraint):
    kind: Literal["foreign_key"] = "foreign_key"
    fields: tuple[str, ...] = Field(min_length=1)
    ref_schema_id: str
    ref_fields: tuple[str, ...] = Field(min_length=1)


class RelationConstraint(_Constraint):
    """Row-wise comparison of two numeric fields.

    Example: ``lead_time_std_days <= lead_time_mean_days``.
    """

    kind: Literal["relation"] = "relation"
    left: str
    op: Literal["<", "<=", "==", ">=", ">"]
    right: str


Constraint = Annotated[
    RangeConstraint
    | NotNullConstraint
    | UniqueConstraint
    | IntegerConstraint
    | ForeignKeyConstraint
    | RelationConstraint,
    Field(discriminator="kind"),
]


class ConstraintSet(_Constraint):
    """An ordered, serialisable collection of constraints."""

    constraints: tuple[Constraint, ...] = ()
