from src.core.bynder_client import BynderAsset
from src.core.bulk_export import build_row, BulkExportRow


def _asset(**overrides) -> BynderAsset:
    defaults = dict(
        asset_id="asset-1",
        filename="806781_01_Front.jpg",
        original_url="",
        sku="806781",
        extension="jpg",
        thumbnail_url="https://cdn/web.jpg",
        tags=("806781", "swappable"),
        metaproperties={"property_SKUs": "806781"},
        raw={
            "id": "asset-1",
            "name": "806781_01_Front",
            "extension": ["jpg"],
            "thumbnails": {"webimage": "https://cdn/web.jpg"},
        },
    )
    defaults.update(overrides)
    return BynderAsset(**defaults)


def test_build_row_basic_shape():
    row = build_row("806781", _asset(), None, ["property_UPC"])
    assert isinstance(row, BulkExportRow)
    assert row.sku == "806781"
    assert row.image_name == "806781_01_Front.jpg"
    assert row.image_link == "https://cdn/web.jpg"
    assert row.tags == "806781; swappable"
    assert row.upc == ""
    assert row.asset_id == "asset-1"


def test_build_row_reads_upc_from_first_matching_key():
    asset = _asset(
        metaproperties={"property_SKUs": "806781", "property_GTIN": "842978104324"},
        raw={
            "id": "asset-1",
            "property_GTIN": "842978104324",
            "thumbnails": {"webimage": "https://cdn/web.jpg"},
        },
    )
    row = build_row("806781", asset, None, ["property_UPC", "property_GTIN"])
    assert row.upc == "842978104324"


def test_build_row_skips_empty_upc_keys():
    asset = _asset(
        metaproperties={"property_UPC": "", "property_GTIN": "842978104324"},
    )
    row = build_row("806781", asset, None, ["property_UPC", "property_GTIN"])
    assert row.upc == "842978104324"


def test_build_row_empty_tags_serialize_to_empty_string():
    row = build_row("806781", _asset(tags=()), None, [])
    assert row.tags == ""


def test_build_row_uses_configured_derivative_url():
    asset = _asset(
        raw={
            "id": "asset-1",
            "original": "",
            "thumbnails": {
                "webimage": "https://cdn/web.jpg",
                "amazon_full": "https://cdn/full.jpg",
            },
        },
    )
    row = build_row("806781", asset, "amazon_full", [])
    assert row.image_link == "https://cdn/full.jpg"
