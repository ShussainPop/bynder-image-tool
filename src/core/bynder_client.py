from dataclasses import dataclass
from pathlib import Path
from typing import Any
import requests


@dataclass(frozen=True)
class BynderAsset:
    asset_id: str
    filename: str
    original_url: str
    sku: str | None
    extension: str


class BynderClient:
    """Thin wrapper around bynder-sdk. SDK is injected for testability.

    Uses bynder-sdk v2.x. If the installed SDK differs, adapt from_permanent_token
    and the media_list call site, but keep the public interface stable."""

    def __init__(self, sdk: Any):
        self._sdk = sdk

    @classmethod
    def from_permanent_token(cls, domain: str, token: str) -> "BynderClient":
        from bynder_sdk import BynderClient as SDK
        sdk = SDK(domain=domain, permanent_token=token)
        return cls(sdk=sdk)

    def search_by_sku(self, sku: str) -> list[BynderAsset]:
        raw = self._sdk.asset_bank_client.media_list({"propertyOptionId": sku})
        return [_to_asset(r) for r in raw if _matches_sku(r, sku)]

    def download_asset(self, asset: BynderAsset, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(asset.original_url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)


def _matches_sku(raw: dict, sku: str) -> bool:
    if raw.get("property_sku") == sku:
        return True
    return False


def _to_asset(raw: dict) -> BynderAsset:
    ext_list = raw.get("extension") or []
    ext = (ext_list[0] if ext_list else "").lower() or _ext_from_url(raw.get("original", ""))
    name = raw.get("name") or ""
    filename = name if name.lower().endswith(f".{ext}") else f"{name}.{ext}"
    return BynderAsset(
        asset_id=raw.get("id", ""),
        filename=filename,
        original_url=raw.get("original", ""),
        sku=raw.get("property_sku"),
        extension=ext,
    )


def _ext_from_url(url: str) -> str:
    if "." not in url:
        return ""
    return url.rsplit(".", 1)[-1].split("?")[0].lower()
