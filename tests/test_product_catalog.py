from pathlib import Path
import pytest
from src.core.product_catalog import ProductCatalog, SkuInfo

FIXTURE = Path(__file__).parent / "fixtures" / "barcelona_sample.xlsx"


def test_excel_lookup_returns_sku_info():
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=None)
    info = cat.lookup("PGR-001")
    assert info.sku == "PGR-001"
    assert info.product_line == "PopGrip Standard"
    assert info.tier == "A"
    assert info.description == "PopGrip Classic Black"


def test_excel_lookup_returns_none_for_missing_sku():
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=None)
    assert cat.lookup("DOES-NOT-EXIST") is None


def test_list_product_lines():
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=None)
    lines = cat.list_product_lines()
    assert set(lines) == {"PopGrip Standard", "Wallet"}


def test_list_tiers():
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=None)
    tiers = cat.list_tiers()
    assert set(tiers) == {"A", "B"}


def test_supabase_takes_precedence_over_excel(mocker):
    supabase_stub = mocker.Mock()
    supabase_stub.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {
            "sku": "PGR-001",
            "seo_cluster_1": "OverrideLine",
            "tier": "Z",
            "item_description": "Overridden",
        }
    ]
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=supabase_stub)
    info = cat.lookup("PGR-001")
    assert info.product_line == "OverrideLine"
    assert info.tier == "Z"


def test_supabase_falls_back_to_excel_on_miss(mocker):
    supabase_stub = mocker.Mock()
    supabase_stub.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    cat = ProductCatalog(xlsx_path=str(FIXTURE), supabase_client=supabase_stub)
    info = cat.lookup("PGR-001")
    assert info.product_line == "PopGrip Standard"
