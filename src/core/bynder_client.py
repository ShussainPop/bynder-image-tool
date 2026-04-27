import logging
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import requests


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BynderAsset:
    asset_id: str
    filename: str
    original_url: str  # may be empty; use download_asset() which resolves the signed URL
    sku: str | None
    extension: str
    thumbnail_url: str = ""  # Bynder 'webimage' CDN URL for preview
    tags: tuple[str, ...] = ()
    metaproperties: dict[str, str] = field(default_factory=dict, hash=False, compare=False)
    raw: dict = field(default_factory=dict, hash=False, compare=False)


class BynderClient:
    """Thin wrapper around bynder-sdk v2.x; SDK is injected for testability.

    Popsockets tenant: SKU metaproperty is named `SKUs` (plural). Query server-side
    with `{'property_SKUs': sku}`. Downloading requires a second call to
    `media_download_url()` because the default list response omits `original`.
    """

    SKU_PROPERTY_KEY = "property_SKUs"
    AMAZON_SAFE_EXTENSIONS = frozenset({"jpg", "jpeg", "png"})

    # Defaults: Bynder allows 4500/5min tenant-wide; stay 10% under.
    DEFAULT_THROTTLE_LIMIT = 4000
    DEFAULT_THROTTLE_WINDOW_SEC = 300.0

    def __init__(
        self,
        sdk: Any,
        throttle_limit: int = DEFAULT_THROTTLE_LIMIT,
        throttle_window_sec: float = DEFAULT_THROTTLE_WINDOW_SEC,
    ):
        self._sdk = sdk
        self._throttle_limit = throttle_limit
        self._throttle_window_sec = throttle_window_sec
        self._call_times: deque[float] = deque()

    @classmethod
    def from_permanent_token(cls, domain: str, token: str) -> "BynderClient":
        from bynder_sdk import BynderClient as SDK
        sdk = SDK(domain=domain, permanent_token=token)
        return cls(sdk=sdk)

    @classmethod
    def from_client_credentials(
        cls, domain: str, client_id: str, client_secret: str
    ) -> "BynderClient":
        from bynder_sdk import BynderClient as SDK
        sdk = SDK(
            domain=domain,
            client_id=client_id,
            client_secret=client_secret,
            client_credentials=True,
        )
        sdk.fetch_token(code=None)
        return cls(sdk=sdk)

    def _throttle(self) -> None:
        now = time.monotonic()
        window_start = now - self._throttle_window_sec
        while self._call_times and self._call_times[0] < window_start:
            self._call_times.popleft()
        if len(self._call_times) >= self._throttle_limit:
            sleep_for = self._throttle_window_sec - (now - self._call_times[0]) + 0.01
            if sleep_for > 0:
                time.sleep(sleep_for)
            now = time.monotonic()
            window_start = now - self._throttle_window_sec
            while self._call_times and self._call_times[0] < window_start:
                self._call_times.popleft()
        self._call_times.append(now)

    def search_by_sku(self, sku: str) -> list[BynderAsset]:
        """Find image assets for a SKU across all tenant tagging conventions.

        The PopSockets tenant stores SKUs in varied places across the historical
        catalog: the `SKUs` metaproperty (canonical), embedded in tag strings,
        inside the description field, or only in the filename. A single keyword
        query hits Bynder's fuzzy full-text index; we filter client-side so only
        assets that actually mention the SKU are returned.
        """
        query = {"keyword": sku, "type": "image"}
        logger.debug("Bynder media_list query: %s", query)
        self._throttle()
        raw = self._sdk.asset_bank_client.media_list(query)
        logger.debug("  -> %d records", len(raw))

        merged: dict[str, dict] = {}
        for r in raw:
            if _matches_sku(r, sku, self.SKU_PROPERTY_KEY):
                merged[r.get("id", "")] = r

        assets = [to_asset(r, self.SKU_PROPERTY_KEY, sku) for r in merged.values()]
        return [a for a in assets if a.extension in self.AMAZON_SAFE_EXTENSIONS]

    def download_asset(self, asset: BynderAsset, dest: Path) -> None:
        url = asset.original_url
        if not url:
            resp = self._sdk.asset_bank_client.media_download_url(asset.asset_id)
            url = resp.get("s3_file") if isinstance(resp, dict) else None
            if not url:
                raise RuntimeError(f"Bynder did not return a download URL for asset {asset.asset_id}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, stream=True, timeout=(10, 60))
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)


def _matches_sku(raw: dict, sku: str, sku_key: str) -> bool:
    """True when the raw Bynder asset mentions the SKU in any indexed location.

    Covers the four storage conventions observed on the PopSockets tenant:
      - property_SKUs (canonical — list membership)
      - tag equal to SKU, or tag containing SKU as a substring
      - description field (e.g. '<SKU> <UPC> <SKU2> <UPC2>')
      - filename anywhere
    For 6-digit numeric PopSockets SKUs the substring collision risk is negligible.
    """
    value = raw.get(sku_key)
    if value == sku:
        return True
    if isinstance(value, list) and sku in value:
        return True
    tags = raw.get("tags") or []
    if isinstance(tags, list):
        for t in tags:
            if sku in str(t):
                return True
    description = raw.get("description") or ""
    if sku in description:
        return True
    name = raw.get("name") or ""
    if sku in name:
        return True
    return False


def to_asset(raw: dict, sku_key: str, searched_sku: str | None = None) -> BynderAsset:
    ext_list = raw.get("extension") or []
    ext = (ext_list[0] if ext_list else "").lower()
    name = raw.get("name") or ""
    if ext and not name.lower().endswith(f".{ext}"):
        filename = f"{name}.{ext}"
    else:
        filename = name
    thumbs = raw.get("thumbnails") or {}
    thumb_url = thumbs.get("webimage") or thumbs.get("thul") or thumbs.get("mini") or ""
    raw_tags = raw.get("tags") or []
    tags = tuple(str(t) for t in raw_tags) if isinstance(raw_tags, list) else ()
    metaproperties = {
        k: _stringify_property(v)
        for k, v in raw.items()
        if k.startswith("property_")
    }
    return BynderAsset(
        asset_id=raw.get("id", ""),
        filename=filename,
        original_url=raw.get("original", ""),
        sku=searched_sku,
        extension=ext,
        thumbnail_url=thumb_url,
        tags=tags,
        metaproperties=metaproperties,
        raw=raw,
    )


def _stringify_property(value) -> str:
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    if value is None:
        return ""
    return str(value)
