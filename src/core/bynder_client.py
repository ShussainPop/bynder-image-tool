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
    original_url: str
    sku: str | None
    extension: str


class BynderClient:
    """Thin wrapper around bynder-sdk v2.x; SDK is injected for testability.

    Bynder metaproperty lookup surface varies by tenant config. The default
    query uses `propertyOptionId` which only works if the SKU is registered as
    the option ID for a metaproperty. If SKU is stored as a free-text
    metaproperty value, override `search_by_sku` or adjust `_matches_sku` to
    match the actual response shape (it can be a scalar, a list of option IDs,
    or nested under `metaproperties`). Log a real response once by running
    `search_by_sku` against a known SKU and inspecting the raw output.
    """

    def __init__(self, sdk: Any):
        self._sdk = sdk

    @classmethod
    def from_permanent_token(cls, domain: str, token: str) -> "BynderClient":
        from bynder_sdk import BynderClient as SDK
        sdk = SDK(domain=domain, permanent_token=token)
        return cls(sdk=sdk)

    def search_by_sku(self, sku: str) -> list[BynderAsset]:
        query = {"propertyOptionId": sku}
        logger.debug("Bynder media_list query: %s", query)
        raw = self._sdk.asset_bank_client.media_list(query)
        logger.debug("Bynder media_list returned %d raw records", len(raw))
        return [_to_asset(r) for r in raw if _matches_sku(r, sku)]

    def download_asset(self, asset: BynderAsset, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(asset.original_url, stream=True, timeout=(10, 60))
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)


def _matches_sku(raw: dict, sku: str) -> bool:
    value = raw.get("property_sku")
    if value == sku:
        return True
    if isinstance(value, list) and sku in value:
        return True
    return False


def _to_asset(raw: dict) -> BynderAsset:
    ext_list = raw.get("extension") or []
    ext = (ext_list[0] if ext_list else "").lower() or _ext_from_url(raw.get("original", ""))
    name = raw.get("name") or ""
    if ext and not name.lower().endswith(f".{ext}"):
        filename = f"{name}.{ext}"
    else:
        filename = name
    sku_raw = raw.get("property_sku")
    sku_value = sku_raw[0] if isinstance(sku_raw, list) and sku_raw else sku_raw
    return BynderAsset(
        asset_id=raw.get("id", ""),
        filename=filename,
        original_url=raw.get("original", ""),
        sku=sku_value if isinstance(sku_value, str) else None,
        extension=ext,
    )


def _ext_from_url(url: str) -> str:
    from urllib.parse import urlparse
    path = urlparse(url).path
    if "." not in path:
        return ""
    return path.rsplit(".", 1)[-1].lower()
