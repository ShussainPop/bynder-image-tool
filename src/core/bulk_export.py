"""Bulk SKU CSV export — framework-agnostic core.

Flow: parse SKUs -> for each SKU call BynderClient.search_by_sku ->
build one CSV row per asset -> serialize to CSV bytes.

Streamlit UI lives in src/ui/bulk_export_tab.py and only orchestrates.
"""
import csv
import io
import re
from dataclasses import dataclass

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
