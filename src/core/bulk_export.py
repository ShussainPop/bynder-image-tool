"""Bulk SKU CSV export — framework-agnostic core.

Flow: parse SKUs -> for each SKU call BynderClient.search_by_sku ->
build one CSV row per asset -> serialize to CSV bytes.

Streamlit UI lives in src/ui/bulk_export_tab.py and only orchestrates.
"""
import csv
import datetime as _dt
import io
import re
from dataclasses import dataclass, field
from typing import Callable, Protocol

from src.core.bynder_client import BynderAsset
from src.core.bynder_urls import resolve_csv_url


MAX_SKUS_PER_RUN = 2000

_HEADER_CANDIDATES = {"sku", "skus"}


def parse_sku_input(text: str) -> list[str]:
    """Split pasted SKU text on whitespace/commas, dedupe case-insensitively."""
    if not text:
        return []
    tokens = [t for t in re.split(r"[\s,]+", text) if t]
    return _dedupe_case_insensitive_over_cap(tokens)


def parse_sku_csv(data: bytes) -> list[str]:
    """Read the first column of a CSV upload. Skip header row if it says 'sku'."""
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if r and any(cell.strip() for cell in r)]
    if not rows:
        return []
    first_cell = rows[0][0].strip().lower()
    if first_cell in _HEADER_CANDIDATES:
        rows = rows[1:]
    skus = [r[0].strip() for r in rows if r and r[0].strip()]
    return _dedupe_case_insensitive_over_cap(skus)


def _dedupe_case_insensitive_over_cap(skus: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for s in skus:
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(s)
    if len(result) > MAX_SKUS_PER_RUN:
        raise ValueError(
            f"too many SKUs: got {len(result)}, max is {MAX_SKUS_PER_RUN}. "
            "Split into smaller batches."
        )
    return result


@dataclass
class BulkExportRow:
    sku: str
    image_name: str
    image_link: str
    tags: str
    upc: str
    asset_id: str


def build_row(
    sku: str,
    asset: BynderAsset,
    derivative_key: str | None,
    upc_keys: list[str],
) -> BulkExportRow:
    image_link = resolve_csv_url(asset.raw, derivative_key)
    upc = _first_non_empty(asset.metaproperties, upc_keys)
    return BulkExportRow(
        sku=sku,
        image_name=asset.filename,
        image_link=image_link,
        tags="; ".join(asset.tags),
        upc=upc,
        asset_id=asset.asset_id,
    )


def _first_non_empty(props: dict[str, str], keys: list[str]) -> str:
    for k in keys:
        v = props.get(k, "")
        if v:
            return v
    return ""


class _SearchClient(Protocol):
    def search_by_sku(self, sku: str) -> list[BynderAsset]: ...


class _AssetCache(Protocol):
    def get_or_fetch(
        self,
        sku: str,
        fetch_fn: Callable[[str], list[BynderAsset]],
        force_refresh: bool = False,
    ) -> tuple[list[BynderAsset], bool]: ...


@dataclass
class BulkExportResult:
    rows: list[BulkExportRow]
    missing_skus: list[str]
    failed_skus: list[tuple[str, str]]
    cache_hits: int = 0
    assets_by_sku: dict[str, list[BynderAsset]] = field(default_factory=dict)


def run_export(
    skus: list[str],
    client: _SearchClient,
    derivative_key: str | None,
    upc_keys: list[str],
    include_missing: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
    cache: _AssetCache | None = None,
    force_refresh: bool = False,
) -> BulkExportResult:
    rows: list[BulkExportRow] = []
    missing: list[str] = []
    failed: list[tuple[str, str]] = []
    assets_by_sku: dict[str, list[BynderAsset]] = {}
    cache_hits = 0
    total = len(skus)

    for i, sku in enumerate(skus, start=1):
        try:
            if cache is not None:
                assets, was_hit = cache.get_or_fetch(
                    sku, client.search_by_sku, force_refresh=force_refresh
                )
                if was_hit:
                    cache_hits += 1
            else:
                assets = client.search_by_sku(sku)
        except Exception as e:
            failed.append((sku, str(e)))
            if on_progress is not None:
                on_progress(i, total)
            continue

        if not assets:
            missing.append(sku)
            if include_missing:
                rows.append(BulkExportRow(
                    sku=sku, image_name="", image_link="",
                    tags="", upc="", asset_id="",
                ))
        else:
            assets_by_sku[sku] = list(assets)
            for a in assets:
                rows.append(build_row(sku, a, derivative_key, upc_keys))

        if on_progress is not None:
            on_progress(i, total)

    return BulkExportResult(
        rows=rows,
        missing_skus=missing,
        failed_skus=failed,
        cache_hits=cache_hits,
        assets_by_sku=assets_by_sku,
    )


CSV_COLUMNS = ["sku", "image_name", "image_link", "tags", "upc", "asset_id"]


def to_csv_bytes(result: BulkExportResult) -> bytes:
    """Serialize to UTF-8 with BOM, RFC4180 quoting."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_COLUMNS)
    for r in result.rows:
        writer.writerow([
            r.sku, r.image_name, r.image_link, r.tags, r.upc, r.asset_id,
        ])
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def export_filename(now: _dt.datetime | None = None) -> str:
    when = now or _dt.datetime.now()
    return when.strftime("bynder_export_%Y-%m-%d_%H%M%S.csv")
