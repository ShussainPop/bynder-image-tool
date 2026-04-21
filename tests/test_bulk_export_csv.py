from src.core.bulk_export import (
    BulkExportResult, BulkExportRow, to_csv_bytes,
)


def _result(rows):
    return BulkExportResult(rows=rows, missing_skus=[], failed_skus=[])


def test_csv_has_utf8_bom():
    data = to_csv_bytes(_result([]))
    assert data.startswith(b"\xef\xbb\xbf"), "CSV must be UTF-8 with BOM for Excel"


def test_csv_header_row_matches_spec():
    data = to_csv_bytes(_result([]))
    first_line = data.decode("utf-8-sig").splitlines()[0]
    assert first_line == "sku,image_name,image_link,tags,upc,asset_id"


def test_csv_rows_are_serialized_in_order():
    rows = [
        BulkExportRow("A", "a.jpg", "https://cdn/a.jpg", "x; y", "111", "id-a"),
        BulkExportRow("B", "b.jpg", "https://cdn/b.jpg", "z", "222", "id-b"),
    ]
    decoded = to_csv_bytes(_result(rows)).decode("utf-8-sig")
    lines = decoded.splitlines()
    assert lines[1] == "A,a.jpg,https://cdn/a.jpg,x; y,111,id-a"
    assert lines[2] == "B,b.jpg,https://cdn/b.jpg,z,222,id-b"


def test_csv_quotes_values_with_commas():
    rows = [BulkExportRow("A", "a,b.jpg", "url", "t1, t2", "", "id-a")]
    decoded = to_csv_bytes(_result(rows)).decode("utf-8-sig")
    assert '"a,b.jpg"' in decoded
    assert '"t1, t2"' in decoded


def test_csv_empty_result_still_has_header():
    decoded = to_csv_bytes(_result([])).decode("utf-8-sig")
    lines = decoded.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("sku,")
