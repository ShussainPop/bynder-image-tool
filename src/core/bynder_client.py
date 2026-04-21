import logging
from dataclasses import dataclass
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


class BynderClient:
    """Thin wrapper around bynder-sdk v2.x; SDK is injected for testability.

    Popsockets tenant: SKU metaproperty is named `SKUs` (plural). Query server-side
    with `{'property_SKUs': sku}`. Downloading requires a second call to
    `media_download_url()` because the default list response omits `original`.
    """

    SKU_PROPERTY_KEY = "property_SKUs"

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
        query = {self.SKU_PROPERTY_KEY: sku, "type": "image"}
        logger.debug("Bynder media_list query: %s", query)
        raw = self._sdk.asset_bank_client.media_list(query)
        logger.debug("Bynder media_list returned %d raw records", len(raw))
        return [_to_asset(r, self.SKU_PROPERTY_KEY) for r in raw if _matches_sku(r, sku, self.SKU_PROPERTY_KEY)]

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
    return False


def _to_asset(raw: dict, sku_key: str) -> BynderAsset:
    ext_list = raw.get("extension") or []
    ext = (ext_list[0] if ext_list else "").lower()
    name = raw.get("name") or ""
    if ext and not name.lower().endswith(f".{ext}"):
        filename = f"{name}.{ext}"
    else:
        filename = name
    sku_raw = raw.get(sku_key)
    sku_value = sku_raw[0] if isinstance(sku_raw, list) and sku_raw else sku_raw
    return BynderAsset(
        asset_id=raw.get("id", ""),
        filename=filename,
        original_url=raw.get("original", ""),
        sku=sku_value if isinstance(sku_value, str) else None,
        extension=ext,
    )
