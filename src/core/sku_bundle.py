"""Per-SKU image bundle (zip) builder for the bulk-export Browse-by-SKU view.

Fetches each Bynder asset's full-res CDN URL via plain HTTP (no Bynder API call —
URLs are public CDN derivatives, so the 4500/5min API throttle does not apply)
and writes the bytes into an in-memory zip suitable for `st.download_button`.
"""
import io
import zipfile
from typing import Callable

import requests

from src.core.bynder_client import BynderAsset
from src.core.bynder_urls import resolve_csv_url


_FetchFn = Callable[[str], bytes]


def _default_fetch(url: str) -> bytes:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def build_sku_zip(
    sku: str,
    assets: list[BynderAsset],
    derivative_key: str | None,
    fetch: _FetchFn | None = None,
) -> bytes:
    """Zip every resolvable asset for `sku` into one archive.

    Arcnames are `<sku>__<filename>` with collisions disambiguated by `(N)`.
    Assets whose URL cannot be resolved are skipped silently.
    Returns empty zip bytes if no assets are downloadable.
    """
    fetcher = fetch or _default_fetch
    used: set[str] = set()
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for asset in assets:
            url = resolve_csv_url(asset.raw, derivative_key)
            if not url:
                continue
            content = fetcher(url)
            arcname = _unique_arcname(sku, asset.filename, used)
            zf.writestr(arcname, content)

    return buf.getvalue()


def _unique_arcname(sku: str, filename: str, used: set[str]) -> str:
    safe = filename.replace("/", "_").replace("\\", "_") or "asset"
    base = f"{sku}__{safe}"
    if base not in used:
        used.add(base)
        return base
    stem, dot, ext = safe.rpartition(".")
    n = 2
    while True:
        candidate = (
            f"{sku}__{stem} ({n}).{ext}" if dot else f"{sku}__{safe} ({n})"
        )
        if candidate not in used:
            used.add(candidate)
            return candidate
        n += 1
