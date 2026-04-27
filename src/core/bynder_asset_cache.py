"""SKU -> Bynder assets cache.

Stores one row per SKU keyed on the SKU itself, with the full list of raw
Bynder asset records as a JSON column. Avoids re-querying Bynder for SKUs we
already have links for (the bulk-export hot path).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.orm import Session

from src.core.bynder_client import BynderAsset, BynderClient, to_asset
from src.db.models import BynderAssetCacheEntry


class BynderAssetCache:
    def __init__(self, session: Session, ttl: timedelta):
        self._session = session
        self._ttl = ttl

    def get(self, sku: str) -> list[BynderAsset] | None:
        """Return cached assets for `sku` if a fresh entry exists, else None."""
        entry = self._session.get(BynderAssetCacheEntry, sku)
        if entry is None:
            return None
        if self._is_stale(entry.cached_at):
            return None
        return [
            to_asset(raw, BynderClient.SKU_PROPERTY_KEY, sku)
            for raw in entry.assets_json
        ]

    def put(self, sku: str, assets: list[BynderAsset]) -> None:
        """Upsert cache entry for `sku`. Empty lists are cached too — that
        records 'Bynder has no assets for this SKU' and prevents re-querying
        until TTL expiry."""
        raw_list = [a.raw for a in assets]
        entry = self._session.get(BynderAssetCacheEntry, sku)
        now = datetime.now(timezone.utc)
        if entry is None:
            entry = BynderAssetCacheEntry(
                sku=sku, assets_json=raw_list, cached_at=now
            )
            self._session.add(entry)
        else:
            entry.assets_json = raw_list
            entry.cached_at = now
        self._session.commit()

    def get_or_fetch(
        self,
        sku: str,
        fetch_fn: Callable[[str], list[BynderAsset]],
        force_refresh: bool = False,
    ) -> tuple[list[BynderAsset], bool]:
        """Return (assets, was_cache_hit). On miss or force_refresh, calls
        `fetch_fn(sku)` and caches the result."""
        if not force_refresh:
            cached = self.get(sku)
            if cached is not None:
                return cached, True
        fresh = fetch_fn(sku)
        self.put(sku, fresh)
        return fresh, False

    def _is_stale(self, cached_at: datetime) -> bool:
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - cached_at > self._ttl
