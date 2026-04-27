import io
import zipfile

import pytest

from src.core.bynder_client import BynderAsset
from src.core.sku_bundle import build_sku_zip


def _asset(asset_id: str, filename: str, *, original: str = "", webimage: str = "") -> BynderAsset:
    raw: dict = {"id": asset_id, "thumbnails": {}}
    if webimage:
        raw["thumbnails"]["webimage"] = webimage
    if original:
        raw["original"] = original
    return BynderAsset(
        asset_id=asset_id,
        filename=filename,
        original_url=original,
        sku=None,
        extension=filename.rsplit(".", 1)[-1] if "." in filename else "",
        thumbnail_url=webimage,
        tags=(),
        metaproperties={},
        raw=raw,
    )


def test_build_sku_zip_writes_one_entry_per_asset():
    assets = [
        _asset("a1", "front.jpg", original="https://cdn/a1.jpg"),
        _asset("a2", "back.png", original="https://cdn/a2.png"),
    ]
    fetched: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched.append(url)
        return f"bytes-of-{url}".encode()

    data = build_sku_zip("806781", assets, derivative_key=None, fetch=fake_fetch)

    assert fetched == ["https://cdn/a1.jpg", "https://cdn/a2.png"]
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        assert names == ["806781__front.jpg", "806781__back.png"]
        assert zf.read("806781__front.jpg") == b"bytes-of-https://cdn/a1.jpg"
        assert zf.read("806781__back.png") == b"bytes-of-https://cdn/a2.png"


def test_build_sku_zip_skips_assets_with_no_resolvable_url():
    assets = [
        _asset("a1", "front.jpg", original="https://cdn/a1.jpg"),
        _asset("a2", "no_url.jpg"),  # neither original nor webimage
    ]

    def fake_fetch(url: str) -> bytes:
        return b"x"

    data = build_sku_zip("S", assets, derivative_key=None, fetch=fake_fetch)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert zf.namelist() == ["S__front.jpg"]


def test_build_sku_zip_disambiguates_duplicate_filenames():
    assets = [
        _asset("a1", "front.jpg", original="https://cdn/a.jpg"),
        _asset("a2", "front.jpg", original="https://cdn/b.jpg"),
        _asset("a3", "front.jpg", original="https://cdn/c.jpg"),
    ]

    def fake_fetch(url: str) -> bytes:
        return url.encode()

    data = build_sku_zip("X", assets, derivative_key=None, fetch=fake_fetch)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert zf.namelist() == [
            "X__front.jpg",
            "X__front (2).jpg",
            "X__front (3).jpg",
        ]


def test_build_sku_zip_uses_derivative_key_when_provided():
    raw = {
        "id": "a1",
        "original": "https://cdn/original.jpg",
        "thumbnails": {
            "webimage": "https://cdn/web.jpg",
            "amazon_full": "https://cdn/derivative.jpg",
        },
    }
    asset = BynderAsset(
        asset_id="a1",
        filename="front.jpg",
        original_url="https://cdn/original.jpg",
        sku=None,
        extension="jpg",
        thumbnail_url="https://cdn/web.jpg",
        tags=(),
        metaproperties={},
        raw=raw,
    )
    fetched: list[str] = []
    build_sku_zip("S", [asset], derivative_key="amazon_full", fetch=lambda u: (fetched.append(u) or b"x"))
    assert fetched == ["https://cdn/derivative.jpg"]


def test_build_sku_zip_propagates_fetch_errors():
    asset = _asset("a1", "front.jpg", original="https://cdn/a1.jpg")

    def boom(url: str) -> bytes:
        raise RuntimeError("network down")

    with pytest.raises(RuntimeError, match="network down"):
        build_sku_zip("S", [asset], derivative_key=None, fetch=boom)


def test_build_sku_zip_empty_assets_returns_valid_empty_zip():
    data = build_sku_zip("S", [], derivative_key=None, fetch=lambda u: b"")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert zf.namelist() == []
