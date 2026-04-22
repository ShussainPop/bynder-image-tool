import json
from pathlib import Path
import pytest
from src.core.bynder_client import BynderClient, BynderAsset

FIXTURE = Path(__file__).parent / "fixtures" / "bynder_media_list.json"


def _fake_media_list_response():
    return json.loads(FIXTURE.read_text())


def test_search_by_sku_returns_assets(mocker):
    fake_sdk = mocker.Mock()
    fake_sdk.asset_bank_client.media_list.return_value = _fake_media_list_response()
    client = BynderClient(sdk=fake_sdk)

    assets = client.search_by_sku("PGR-001")
    assert len(assets) == 2
    assert assets[0].asset_id == "asset-001"
    assert assets[0].filename == "PCS_Derpy-and-Sussie_IP14_01_Front.png"
    assert assets[0].sku == "PGR-001"


def test_search_by_sku_returns_empty_on_miss(mocker):
    fake_sdk = mocker.Mock()
    fake_sdk.asset_bank_client.media_list.return_value = []
    client = BynderClient(sdk=fake_sdk)
    assert client.search_by_sku("NOPE") == []


def test_download_asset_streams_to_path(mocker, tmp_path):
    fake_sdk = mocker.Mock()
    client = BynderClient(sdk=fake_sdk)

    fake_resp = mocker.Mock()
    fake_resp.iter_content.return_value = [b"\x89PNG", b"\x00\x00"]
    fake_resp.raise_for_status = mocker.Mock()
    mocker.patch("src.core.bynder_client.requests.get", return_value=fake_resp)

    asset = BynderAsset(
        asset_id="a",
        filename="x.png",
        original_url="https://example/x.png",
        sku="PGR-001",
        extension="png",
    )
    dest = tmp_path / "x.png"
    client.download_asset(asset, dest)
    assert dest.read_bytes() == b"\x89PNG\x00\x00"


def test_to_asset_captures_tags_and_metaproperties(mocker):
    raw = {
        "id": "asset-010",
        "name": "PCS_TEST_01_Front",
        "type": "image",
        "extension": ["jpg"],
        "property_SKUs": ["SKU-010"],
        "property_UPC": "842978104324",
        "property_Color": ["Black", "Carbon"],
        "tags": ["SKU-010", "swappable", "case"],
    }
    fake_sdk = mocker.Mock()
    fake_sdk.asset_bank_client.media_list.return_value = [raw]
    client = BynderClient(sdk=fake_sdk)

    assets = client.search_by_sku("SKU-010")
    assert len(assets) == 1
    a = assets[0]
    assert a.tags == ("SKU-010", "swappable", "case")
    assert a.metaproperties["property_UPC"] == "842978104324"
    assert a.metaproperties["property_Color"] == "Black; Carbon"
    assert a.metaproperties["property_SKUs"] == "SKU-010"


def test_bynder_asset_is_hashable_even_with_metaproperties():
    asset = BynderAsset(
        asset_id="a",
        filename="f.jpg",
        original_url="",
        sku="S",
        extension="jpg",
        metaproperties={"property_UPC": "123"},
    )
    # Must not raise TypeError: unhashable type: 'dict'
    hash(asset)
    assert asset in {asset}


def test_stringify_property_handles_none_list_and_scalar():
    from src.core.bynder_client import _stringify_property
    assert _stringify_property(None) == ""
    assert _stringify_property(["a", "b"]) == "a; b"
    assert _stringify_property("x") == "x"
    assert _stringify_property(42) == "42"


def test_search_by_sku_matches_all_tenant_tagging_conventions(mocker):
    """PopSockets tenant stores SKUs in varied places across historical catalog."""
    sku = "806777"
    raw_canonical = {
        "id": "a1",
        "name": "canonical.jpg",
        "extension": ["jpg"],
        "property_SKUs": [sku],
    }
    raw_tag_substring = {
        "id": "a2",
        "name": "item.jpg",
        "extension": ["jpg"],
        "tags": [f"{sku} MS CIR-Adapter Ring White-1PK"],
    }
    raw_description = {
        "id": "a3",
        "name": "generic.jpg",
        "extension": ["jpg"],
        "description": f"{sku} 842978104324 806778 842978104331",
    }
    raw_filename = {
        "id": "a4",
        "name": f"{sku}_Photo_01_1x1.jpg",
        "extension": ["jpg"],
    }
    raw_unrelated = {
        "id": "a5",
        "name": "unrelated.jpg",
        "extension": ["jpg"],
        "tags": ["MKTGRevisit"],
        "description": "nothing to see here",
    }

    fake_sdk = mocker.Mock()
    fake_sdk.asset_bank_client.media_list.return_value = [
        raw_canonical, raw_tag_substring, raw_description, raw_filename, raw_unrelated,
    ]
    client = BynderClient(sdk=fake_sdk)

    assets = client.search_by_sku(sku)
    ids = {a.asset_id for a in assets}
    assert ids == {"a1", "a2", "a3", "a4"}, f"expected all 4 legacy patterns to match, got {ids}"

    # Must be a single keyword query (not tags + property_SKUs)
    called_queries = [c.args[0] for c in fake_sdk.asset_bank_client.media_list.call_args_list]
    assert len(called_queries) == 1, f"expected 1 query, got {len(called_queries)}"
    assert "keyword" in called_queries[0]
    assert called_queries[0]["keyword"] == sku


def test_throttle_blocks_when_window_full(mocker):
    # Patch the clock so "now" advances deterministically.
    clock = {"t": 1000.0}
    def fake_monotonic():
        return clock["t"]
    sleeps: list[float] = []
    def fake_sleep(s):
        sleeps.append(s)
        clock["t"] += s

    mocker.patch("src.core.bynder_client.time.monotonic", side_effect=fake_monotonic)
    mocker.patch("src.core.bynder_client.time.sleep", side_effect=fake_sleep)

    fake_sdk = mocker.Mock()
    fake_sdk.asset_bank_client.media_list.return_value = []
    client = BynderClient(sdk=fake_sdk, throttle_limit=1, throttle_window_sec=5.0)

    # search_by_sku fires 1 _throttle() call (single keyword query).
    # With throttle_limit=1, the first call fills the window exactly — no sleep yet.
    client.search_by_sku("A")
    assert sleeps == [], f"no sleep should fire until window overflows; got {sleeps}"

    # Second search finds the deque at the limit and must sleep until the
    # oldest slot ages out of the 5s window.
    client.search_by_sku("B")
    assert len(sleeps) >= 1
    assert sleeps[0] > 0.0
