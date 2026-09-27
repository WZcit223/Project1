"""Dataset schemas (docs/data-model.md §1.1–1.2)."""

import re
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from industrial_ai.core.versioning import parse_version

_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


class DType(StrEnum):
    """Logical column types."""

    INT = "int"
    FLOAT = "float"
    STR = "str"
    BOOL = "bool"
    DATE = "date"
    DATETIME = "datetime"
    CATEGORY = "category"


class FieldSpec(BaseModel):
    """One column of a dataset schema."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    dtype: DType
    nullable: bool = False
    unit: str | None = None
    min: float | None = None
    max: float | None = None
    allowed_values: tuple[str, ...] | None = None
    description: str = ""

    @field_validator("name")
    @classmethod
    def _snake_case(cls, value: str) -> str:
        if not _SNAKE_CASE.fullmatch(value):
            raise ValueError(f"field name {value!r} must be snake_case")
        return value

    @model_validator(mode="after")
    def _consistent_constraints(self) -> Self:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"field {self.name!r}: min {self.min} > max {self.max}")
        if (self.min is not None or self.max is not None) and self.dtype not in (
            DType.INT,
            DType.FLOAT,
        ):
            raise ValueError(f"field {self.name!r}: min/max only apply to int and float fields")
        return self


class ForeignKey(BaseModel):
    """``fields`` of this schema reference ``ref_fields`` of schema ``ref_schema_id``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fields: tuple[str, ...] = Field(min_length=1)
    ref_schema_id: str
    ref_fields: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _same_arity(self) -> Self:
        if len(self.fields) != len(self.ref_fields):
            raise ValueError("foreign key fields and ref_fields must have the same length")
        return self


class DatasetSchema(BaseModel):
    """Versioned schema of one table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_id: str
    schema_version: str
    fields: tuple[FieldSpec, ...] = Field(min_length=1)
    primary_key: tuple[str, ...] = ()
    foreign_keys: tuple[ForeignKey, ...] = ()
    time_index: str | None = None
    entity_keys: tuple[str, ...] = ()
    description: str = ""

    @field_validator("schema_version")
    @classmethod
    def _semver(cls, value: str) -> str:
        parse_version(value)
        return value

    @model_validator(mode="after")
    def _references_exist(self) -> Self:
        names = [f.name for f in self.fields]
        if len(set(names)) != len(names):
            raise ValueError(f"schema {self.schema_id!r} has duplicate field names")
        referenced = [
            *self.primary_key,
            *self.entity_keys,
            *(field for fk in self.foreign_keys for field in fk.fields),
            *([self.time_index] if self.time_index else []),
        ]
        unknown = sorted(set(referenced) - set(names))
        if unknown:
            raise ValueError(f"schema {self.schema_id!r} references unknown fields {unknown}")
        return self

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    def field(self, name: str) -> FieldSpec:
        """The field called ``name``; raises ``KeyError`` if absent."""
        for spec in self.fields:
            if spec.name == name:
                return spec
        raise KeyError(f"schema {self.schema_id!r} has no field {name!r}")
