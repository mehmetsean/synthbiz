import json

from synthbiz.schema import (
    LABEL_COLUMNS,
    TABLE_NAMES,
    columns,
    data_dictionary,
    schema_dict,
)


def test_all_tables_present() -> None:
    expected = {
        "chart_of_accounts", "journal_lines", "vendors", "ap_invoices",
        "ap_payments", "customers", "ar_invoices", "ar_receipts",
        "bank_transactions", "reconciling_items",
    }  # fmt: skip
    assert set(TABLE_NAMES) == expected


def test_schema_is_json_and_complete() -> None:
    s = json.loads(json.dumps(schema_dict()))
    assert s["synthetic"] is True
    for name in TABLE_NAMES:
        t = s["tables"][name]
        assert t["description"]
        for c in t["columns"]:
            assert c["type"] in {"string", "integer", "date"}
            assert c["description"]
        names = [c["name"] for c in t["columns"]]
        assert all(k in names for k in t["primary_key"])


def test_columns_helper() -> None:
    assert columns("vendors")[0] == "vendor_id"
    assert LABEL_COLUMNS == ["table", "row_id", "anomaly_type", "details"]


def test_data_dictionary_lists_every_table_and_column() -> None:
    s = schema_dict()
    md = data_dictionary(s)
    assert "synthetic" in md.lower()
    for name in TABLE_NAMES:
        assert f"## {name}" in md
        for c in columns(name):
            assert f"`{c}`" in md
