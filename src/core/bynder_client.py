import logging
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

    def __init__(self, sdk: Any):
        self._sdk = sdk

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

    def search_by_sku(self, sku: str) -> list[BynderAsset]:
        """Find image assets for a SKU across both metaproperty and tags.

        The popsockets tenant tags newer product photos with the SKU string
        (e.g. tag '806781') while older/related assets may only carry the SKU
        under `property_SKUs`. Query both and merge by asset id.
        """
        merged: dict[str, dict] = {}
        for query in (
            {"tags": sku, "type": "image"},
            {self.SKU_PROPERTY_KEY: sku, "type": "image"},
        ):
            logger.debug("Bynder media_list query: %s", query)
            raw = self._sdk.asset_bank_client.media_list(query)
            logger.debug("  -> %d records", len(raw))
            for r in raw:
                if _matches_sku(r, sku, self.SKU_PROPERTY_KEY):
                    merged[r.get("id", "")] = r

        assets = [_to_asset(r, self.SKU_PROPERTY_KEY, sku) for r in merged.values()]
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
    value = raw.get(sku_key)
    if value == sku:
        return True
    if isinstance(value, list) and sku in value:
        return True
    tags = raw.get("tags") or []
    if isinstance(tags, list) and sku in tags:
        return True
    return False


def _to_asset(raw: dict, sku_key: str, searched_sku: str | None = None) -> BynderAsset:
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
