"""Tests for the canonical retail schemas of the warehouse pack."""

from industrial_ai_warehouse.schemas import RETAIL_SCHEMAS


def test_schema_ids_match_table_names() -> None:
    for table, schema in RETAIL_SCHEMAS.items():
        assert schema.schema_id == f"retail.{table}"
        assert schema.schema_version == "1.0.0"


def test_foreign_keys_reference_known_tables_and_fields() -> None:
    by_id = {schema.schema_id: schema for schema in RETAIL_SCHEMAS.values()}
    for schema in RETAIL_SCHEMAS.values():
        for fk in schema.foreign_keys:
            target = by_id[fk.ref_schema_id]
            assert set(fk.ref_fields) <= set(target.field_names)
            assert tuple(fk.ref_fields) == target.primary_key, (schema.schema_id, fk)


def test_sales_is_a_daily_series_per_product_and_store() -> None:
    sales = RETAIL_SCHEMAS["sales"]
    assert sales.time_index == "date"
    assert sales.entity_keys == ("product_id", "store_id")
    assert sales.field("quantity").min == 0
