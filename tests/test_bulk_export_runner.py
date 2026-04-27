from src.core.bynder_client import BynderAsset
from src.core.bulk_export import run_export, BulkExportResult


class FakeClient:
    """Lightweight stand-in for BynderClient in tests."""
    def __init__(self, result_map=None, errors=None):
        self._results = result_map or {}
        self._errors = errors or {}
        self.calls: list[str] = []

    def search_by_sku(self, sku: str):
        self.calls.append(sku)
        if sku in self._errors:
            raise self._errors[sku]
        return self._results.get(sku, [])


def _asset(asset_id: str, sku: str) -> BynderAsset:
    return BynderAsset(
        asset_id=asset_id,
        filename=f"{sku}_{asset_id}.jpg",
        original_url="",
        sku=sku,
        extension="jpg",
        thumbnail_url="https://cdn/web.jpg",
        tags=(sku,),
        metaproperties={},
        raw={"id": asset_id, "thumbnails": {"webimage": "https://cdn/web.jpg"}},
    )


def test_run_export_collects_rows_per_sku():
    client = FakeClient(
        result_map={
            "A": [_asset("a1", "A"), _asset("a2", "A")],
            "B": [_asset("b1", "B")],
        }
    )
    result = run_export(
        skus=["A", "B"],
        client=client,
        derivative_key=None,
        upc_keys=[],
    )
    assert isinstance(result, BulkExportResult)
    assert len(result.rows) == 3
    assert [r.sku for r in result.rows] == ["A", "A", "B"]
    assert result.missing_skus == []
    assert result.failed_skus == []


def test_run_export_records_missing_skus_without_emitting_rows_by_default():
    client = FakeClient(result_map={"A": [_asset("a1", "A")]})
    result = run_export(
        skus=["A", "ZZZ"],
        client=client,
        derivative_key=None,
        upc_keys=[],
    )
    assert len(result.rows) == 1
    assert result.missing_skus == ["ZZZ"]


def test_run_export_emits_blank_rows_when_include_missing_true():
    client = FakeClient(result_map={})
    result = run_export(
        skus=["X"],
        client=client,
        derivative_key=None,
        upc_keys=[],
        include_missing=True,
    )
    assert len(result.rows) == 1
    r = result.rows[0]
    assert r.sku == "X"
    assert r.image_name == ""
    assert r.image_link == ""
    assert r.tags == ""
    assert r.upc == ""
    assert r.asset_id == ""


def test_run_export_records_failures_and_continues():
    client = FakeClient(
        result_map={"A": [_asset("a1", "A")]},
        errors={"B": RuntimeError("rate limited")},
    )
    result = run_export(
        skus=["A", "B", "C"],
        client=client,
        derivative_key=None,
        upc_keys=[],
    )
    assert [r.sku for r in result.rows] == ["A"]
    assert result.missing_skus == ["C"]
    assert len(result.failed_skus) == 1
    assert result.failed_skus[0][0] == "B"
    assert "rate limited" in result.failed_skus[0][1]


def test_run_export_reports_progress():
    client = FakeClient(result_map={s: [] for s in ["A", "B", "C"]})
    seen: list[tuple[int, int]] = []
    run_export(
        skus=["A", "B", "C"],
        client=client,
        derivative_key=None,
        upc_keys=[],
        on_progress=lambda done, total: seen.append((done, total)),
    )
    assert seen == [(1, 3), (2, 3), (3, 3)]


class FakeCache:
    """Simple in-memory cache implementing the _AssetCache protocol."""
    def __init__(self, prefilled=None):
        self._store = dict(prefilled or {})
        self.calls: list[tuple[str, bool]] = []

    def get_or_fetch(self, sku, fetch_fn, force_refresh=False):
        self.calls.append((sku, force_refresh))
        if not force_refresh and sku in self._store:
            return self._store[sku], True
        fresh = fetch_fn(sku)
        self._store[sku] = fresh
        return fresh, False


def test_run_export_uses_cache_and_reports_hits():
    cached_assets = [_asset("a1", "A"), _asset("a2", "A")]
    cache = FakeCache(prefilled={"A": cached_assets})
    client = FakeClient(result_map={"B": [_asset("b1", "B")]})

    result = run_export(
        skus=["A", "B"],
        client=client,
        derivative_key=None,
        upc_keys=[],
        cache=cache,
    )

    # A served from cache → no Bynder call. B was a miss → one call.
    assert client.calls == ["B"]
    assert result.cache_hits == 1
    assert len(result.rows) == 3


def test_run_export_force_refresh_bypasses_cache():
    cache = FakeCache(prefilled={"A": [_asset("stale", "A")]})
    client = FakeClient(result_map={"A": [_asset("fresh", "A")]})

    result = run_export(
        skus=["A"],
        client=client,
        derivative_key=None,
        upc_keys=[],
        cache=cache,
        force_refresh=True,
    )

    assert client.calls == ["A"]
    assert result.cache_hits == 0
    assert result.rows[0].asset_id == "fresh"


def test_run_export_without_cache_keeps_zero_hits():
    client = FakeClient(result_map={"A": [_asset("a1", "A")]})
    result = run_export(
        skus=["A"],
        client=client,
        derivative_key=None,
        upc_keys=[],
    )
    assert result.cache_hits == 0
