"""Helpers shared by the built-in generators."""

import pandas as pd

from industrial_ai.core.errors import GeneratorParameterError
from industrial_ai.foundation.datasets import Dataset, DatasetBundle, DatasetSchema


def reference_table(
    reference: Dataset | DatasetBundle | None, table: str | None, generator_id: str
) -> Dataset | None:
    """The reference dataset to use: the dataset itself, or ``table`` of a bundle."""
    if reference is None:
        if table is not None:
            raise GeneratorParameterError(
                f"{generator_id}: reference_table set but no reference given"
            )
        return None
    if isinstance(reference, Dataset):
        return reference
    if table is None:
        raise GeneratorParameterError(
            f"{generator_id}: reference is bundle {reference.ref}; set reference_table "
            f"(one of {sorted(reference.tables)})"
        )
    return reference.table(table)


def check_columns(columns: list[str], schema: DatasetSchema, generator_id: str) -> None:
    """Generated columns must be exactly the schema's fields."""
    missing = sorted(set(schema.field_names) - set(columns))
    extra = sorted(set(columns) - set(schema.field_names))
    if missing or extra:
        raise GeneratorParameterError(
            f"{generator_id}: columns do not match schema {schema.schema_id} "
            f"(missing {missing}, unexpected {extra})"
        )


def ordered(frame: pd.DataFrame, schema: DatasetSchema) -> pd.DataFrame:
    return frame.loc[:, list(schema.field_names)]
