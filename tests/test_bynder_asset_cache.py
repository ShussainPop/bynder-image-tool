from datetime import datetime, timedelta, timezone

import pytest

from src.core.bynder_asset_cache import BynderAssetCache
from src.core.bynder_client import BynderAsset
from src.db.models import BynderAssetCacheEntry


def _raw(asset_id: str, sku: str) -> dict:
    return {
        "id": asset_id,
        "name": f"{sku}_{asset_id}",
        "extension": ["jpg"],
        "tags": [sku],
        "property_SKUs": [sku],
        "thumbnails": {"webimage": f"https://cdn/{asset_id}.jpg"},
    }


def _asset(asset_id: str, sku: str) -> BynderAsset:
    return BynderAsset(
        asset_id=asset_id,
        filename=f"{sku}_{asset_id}.jpg",
        original_url="",
        sku=sku,
        extension="jpg",
        thumbnail_url=f"https://cdn/{asset_id}.jpg",
        tags=(sku,),
        metaproperties={"property_SKUs": sku},
        raw=_raw(asset_id, sku),
    )


def test_get_returns_none_on_miss(db_session):
    cache = BynderAssetCache(session=db_session, ttl=timedelta(days=7))
    assert cache.get("UNSEEN") is None


def test_put_then_get_round_trips_assets(db_session):
    cache = BynderAssetCache(session=db_session, ttl=timedelta(days=7))
    cache.put("A", [_asset("a1", "A"), _asset("a2", "A")])

    got = cache.get("A")
    assert got is not None
    assert [a.asset_id for a in got] == ["a1", "a2"]
    assert all(a.sku == "A" for a in got)
    assert got[0].filename == "A_a1.jpg"


def test_put_overwrites_existing_entry(db_session):
    cache = BynderAssetCache(session=db_session, ttl=timedelta(days=7))
    cache.put("A", [_asset("old", "A")])
    cache.put("A", [_asset("new1", "A"), _asset("new2", "A")])

    got = cache.get("A")
    assert [a.asset_id for a in got] == ["new1", "new2"]


def test_get_returns_none_when_entry_is_stale(db_session):
    cache = BynderAssetCache(session=db_session, ttl=timedelta(hours=1))
    cache.put("A", [_asset("a1", "A")])

    # Manually backdate the cached_at to make it stale.
    entry = db_session.get(BynderAssetCacheEntry, "A")
    entry.cached_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    assert cache.get("A") is None


def test_empty_results_are_cached_to_avoid_requerying(db_session):
    cache = BynderAssetCache(session=db_session, ttl=timedelta(days=7))
    cache.put("ZZZ", [])

    got = cache.get("ZZZ")
    assert got == []  # not None — empty hit, not a miss


def test_get_or_fetch_calls_fetch_fn_on_miss_and_stores(db_session):
    cache = BynderAssetCache(session=db_session, ttl=timedelta(days=7))
    calls: list[str] = []

    def fetch(sku):
        calls.append(sku)
        return [_asset("fresh", sku)]

    assets, was_hit = cache.get_or_fetch("A", fetch)
    assert calls == ["A"]
    assert was_hit is False
    assert [a.asset_id for a in assets] == ["fresh"]
    # Subsequent call hits the cache.
    assets2, was_hit2 = cache.get_or_fetch("A", fetch)
    assert calls == ["A"]
    assert was_hit2 is True
    assert [a.asset_id for a in assets2] == ["fresh"]


def test_get_or_fetch_force_refresh_bypasses_cache(db_session):
    cache = BynderAssetCache(session=db_session, ttl=timedelta(days=7))
    cache.put("A", [_asset("stale", "A")])

    fetched: list[str] = []

    def fetch(sku):
        fetched.append(sku)
        return [_asset("refreshed", sku)]

    assets, was_hit = cache.get_or_fetch("A", fetch, force_refresh=True)
    assert fetched == ["A"]
    assert was_hit is False
    assert [a.asset_id for a in assets] == ["refreshed"]
    # Cache was rewritten to the refreshed value.
    assert [a.asset_id for a in cache.get("A")] == ["refreshed"]
