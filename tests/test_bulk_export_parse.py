import pytest
from src.core.bulk_export import parse_sku_input, parse_sku_csv, MAX_SKUS_PER_RUN


def test_parse_newline_delimited():
    assert parse_sku_input("806781\n806782\n806783") == ["806781", "806782", "806783"]


def test_parse_comma_delimited():
    assert parse_sku_input("806781, 806782 , 806783") == ["806781", "806782", "806783"]


def test_parse_mixed_whitespace_and_commas():
    assert parse_sku_input("806781\n  806782,806783\t806784") == [
        "806781", "806782", "806783", "806784"
    ]


def test_parse_strips_blank_lines():
    assert parse_sku_input("\n806781\n\n\n806782\n") == ["806781", "806782"]


def test_parse_dedupes_case_insensitively_preserves_first_casing():
    assert parse_sku_input("ABC-1\nabc-1\nABC-1") == ["ABC-1"]


def test_parse_empty_returns_empty_list():
    assert parse_sku_input("") == []
    assert parse_sku_input("   \n\n  ") == []


def test_parse_raises_over_cap():
    many = "\n".join(f"sku-{i}" for i in range(MAX_SKUS_PER_RUN + 1))
    with pytest.raises(ValueError, match="too many"):
        parse_sku_input(many)


def test_parse_csv_with_sku_header_takes_first_column():
    data = b"sku\n806781\n806782\n"
    assert parse_sku_csv(data) == ["806781", "806782"]


def test_parse_csv_uppercase_header():
    data = b"SKU\n806781\n806782\n"
    assert parse_sku_csv(data) == ["806781", "806782"]


def test_parse_csv_without_header_uses_first_row():
    data = b"806781\n806782\n"
    assert parse_sku_csv(data) == ["806781", "806782"]


def test_parse_csv_ignores_extra_columns():
    data = b"sku,name\n806781,Phone Grip\n806782,Case\n"
    assert parse_sku_csv(data) == ["806781", "806782"]


def test_parse_csv_skips_blank_rows():
    data = b"sku\n806781\n\n806782\n"
    assert parse_sku_csv(data) == ["806781", "806782"]


def test_parse_csv_handles_utf8_bom():
    data = b"\xef\xbb\xbfsku\n806781\n"
    assert parse_sku_csv(data) == ["806781"]
