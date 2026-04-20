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
